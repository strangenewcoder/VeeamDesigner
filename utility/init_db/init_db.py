"""
Initialize VeeamDesigner tables and populate ports_definitions.
"""

import argparse
import csv
import os
from pathlib import Path
import re
import sqlite3
import sys

import eprint
from role_mappings import ROLE_MAPPINGS


def get_cli_arguments():
    """
    Parse and return CLI arguments.
    """

    parser = argparse.ArgumentParser(
        description="Initialize VeeamDesigner tables and populate ports_definitions."
    )
    parser.add_argument(
        "-f",
        "--dbfilename",
        required=True,
        help="Database file name.",
    )

    return parser.parse_args()


def opendb(file_name):
    """
    Validate and connect to an existing SQLite database.

    Raises:
        FileNotFoundError: if the file does not exist.
        RuntimeError: if the file is not a valid SQLite database.
    """

    if not os.path.exists(file_name):
        raise FileNotFoundError(f"Database file not found: '{file_name}'")

    # quick check: SQLite files start with "SQLite format 3"
    with open(file_name, "rb") as f:
        header = f.read(16)
    if not header.startswith(b"SQLite format 3"):
        raise RuntimeError(f"File is not a valid SQLite database: '{file_name}'")

    db_conn = sqlite3.connect(file_name)
    eprint.eprint(f"[INFO] Connected to: {file_name}")

    return db_conn


def create_tables(db_conn):
    """
    Drop and recreate VeeamDesigner working tables (ports_definitions, systems, mappings).
    """

    cursor = db_conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS ports_definitions")
    cursor.execute("""
        CREATE TABLE ports_definitions (
            id             INTEGER PRIMARY KEY,
            product        TEXT,
            sourceservice  TEXT,
            targetservice  TEXT,
            protocol       TEXT,
            original_port  TEXT,
            description    TEXT,
            from_role      TEXT,
            to_role        TEXT,
            ports          TEXT
        )
    """)
    eprint.eprint("[DB] Table 'ports_definitions' recreated.")

    cursor.execute("DROP TABLE IF EXISTS systems")
    cursor.execute("""
        CREATE TABLE systems (
            drawings   TEXT,
            name       TEXT,
            ip         TEXT,
            role       TEXT,
            mainrole   INT
        )
    """)
    eprint.eprint("[DB] Table 'systems' recreated.")

    cursor.execute("DROP TABLE IF EXISTS mappings")
    cursor.execute("""
        CREATE TABLE mappings (
            from_name  TEXT,
            from_role  TEXT,
            from_ip    TEXT,
            to_name    TEXT,
            to_role    TEXT,
            to_ip      TEXT
        )
    """)
    eprint.eprint("[DB] Table 'mappings' recreated.")

    cursor.execute("DROP TABLE IF EXISTS role_propagations")
    cursor.execute("""
        CREATE TABLE role_propagations(
            master_role  TEXT,
            added_role TEXT
        )
    """)
    eprint.eprint("[DB] Table 'role_propagations' recreated.")

    db_conn.commit()
    cursor.close()


def process_port(port):
    """
    Normalize a raw port string from all_ports into a clean ports value.

    Processing steps:
        1. If no digits found — descriptive string, return as-is.
        2. Replace 'or' with comma.
        3. Replace N+ patterns with 'N to N+1000' ranges.
        3b. Normalize dash ranges: N-N → N to N.
        4. Parentheses: discard if starts with 'for'; keep if purely digits;
           extract first number if digits present; discard otherwise.
        5. Normalize whitespace.
        6. Normalize commas: remove spaces before comma, ensure one space after.
        7. Split by comma or space into tokens.
        8. Merge tokens around 'to' into ranges; discard non-numeric tokens.
        9. Join with ', ' and strip trailing comma/whitespace.

    Args:
        port: raw port string from all_ports.

    Returns:
        Normalized port string.
    """

    if port is None:
        return ""

    value = port.strip()

    # Step 1 — no digits: descriptive string, return as-is
    if not re.search(r"\d", value):
        return value

    # Step 2 — replace 'or' with comma
    value = re.sub(r"\bor\b", ",", value, flags=re.IGNORECASE)

    # Step 3 — replace N+ with N to N+1000 (e.g. 1100+ → 1100 to 2100)
    def expand_plus(m):
        base = int(m.group(1))
        return f"{base} to {base + 1000}"

    value = re.sub(r"(\d+)\+", expand_plus, value)

    # Step 3b — normalize dash ranges: 2500-3300 → 2500 to 3300
    value = re.sub(r"(\d+)\s*-\s*(\d+)", r"\1 to \2", value)

    # Step 4 — parentheses handling:
    #   - starts with 'for' → discard (descriptive clause, e.g. "for Windows Server 2012")
    #   - purely digits     → keep as port number
    #   - contains digits   → extract first number (e.g. "5986 - used by default")
    #   - no digits         → discard (e.g. "HTTPS", "SMB")
    def handle_parens(m):
        inner = m.group(1).strip()
        if re.match(r"for\b", inner, flags=re.IGNORECASE):
            return ""
        if re.fullmatch(r"\d+", inner):
            return f" {inner}"
        num = re.search(r"\d+", inner)
        return f" {num.group(0)}" if num else ""

    value = re.sub(r"\(([^)]*)\)", handle_parens, value)

    # Step 5 — normalize whitespace
    value = re.sub(r"\s+", " ", value).strip()

    # Step 6 — normalize commas: remove spaces before comma, ensure one space after
    value = re.sub(r"\s*,\s*", ", ", value)

    # Step 7 — split by comma or space into tokens
    raw_tokens = re.split(r",\s*|\s+", value)
    raw_tokens = [t.strip() for t in raw_tokens if t.strip()]

    # Step 8 — merge tokens around 'to' to preserve ranges; discard non-numeric junk tokens
    tokens = []
    i = 0
    while i < len(raw_tokens):
        if (
            i + 2 < len(raw_tokens)
            and raw_tokens[i + 1].lower() == "to"
            and re.fullmatch(r"\d+", raw_tokens[i])
            and re.fullmatch(r"\d+", raw_tokens[i + 2])
        ):
            tokens.append(f"{raw_tokens[i]} to {raw_tokens[i + 2]}")
            i += 3
        elif re.fullmatch(r"\d+", raw_tokens[i]):
            tokens.append(raw_tokens[i])
            i += 1
        else:
            i += 1  # discard non-numeric token (e.g. "and", "other")

    # Step 9 — join with ', ' and strip trailing comma/whitespace
    result = ", ".join(tokens)
    result = result.strip(", ").strip()

    return result


def resolve_role(service):
    """
    Resolve a service name to a role identifier using ROLE_MAPPINGS.

    All patterns in ROLE_MAPPINGS are evaluated in order.
    % in a pattern key is treated as a wildcard (prefix, suffix, or both).
    Matching is case-insensitive. Last match wins.

    Args:
        service: raw service name string (e.g. from sourceservice column).

    Returns:
        Role string (e.g. 'VBRBACKUPSERVER'), or '' if nothing matched.
    """

    if not service:
        return ""

    role = ""
    service_lower = service.lower()
    for pattern, mapped_role in ROLE_MAPPINGS.items():
        pattern_lower = pattern.lower()
        has_prefix_wildcard = pattern_lower.startswith("%")
        has_suffix_wildcard = pattern_lower.endswith("%")
        literal = pattern_lower.strip("%")

        if has_prefix_wildcard and has_suffix_wildcard:
            match = literal in service_lower
        elif has_prefix_wildcard:
            match = service_lower.endswith(literal)
        elif has_suffix_wildcard:
            match = service_lower.startswith(literal)
        else:
            match = service_lower == literal

        if match:
            role = mapped_role

    return role


def populate_role_propagations(db_conn, role_propagations_file):
    """
    Populated the role_propagations definitions.
    """

    cur = db_conn.cursor()

    with open(role_propagations_file, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        rows = [tuple(row) for row in reader if row]  # skip empty lines

    cur.executemany(
        "INSERT INTO role_propagations (master_role, added_role) VALUES (?, ?)", rows
    )
    db_conn.commit()
    eprint.eprint(f"[DB] populate_role_propagations: Inserted {len(rows)} rows.")

    cur.close()


def populate_ports_definitions(db_conn):
    """
    Read all_ports and insert processed rows into ports_definitions.

    Columns copied:
        product, sourceservice, targetservice, protocol,
        original_port (= port), description
    Columns computed:
        ports     = process_port(port)
        from_role = resolve_role(sourceservice)
        to_role   = resolve_role(targetservice)

    If sourceservice contains multiple comma-separated values (e.g.
    "aaa, bbb"), one row is inserted per value, each with its own
    sourceservice / from_role, and the rest of the fields unchanged.

    If targetservice contains multiple comma-separated values (e.g.
    "aaa, bbb"), one row is inserted per value, each with its own
    targetservice / from_role, and the rest of the fields unchanged.

    Raises:
        sqlite3.OperationalError: if the all_ports table is missing.
    """

    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT product, sourceservice, targetservice, protocol, port, description
        FROM all_ports
    """)
    rows = cursor.fetchall()

    inserted = 0
    for product, sourceservice, targetservice, protocol, port, description in rows:
        ports = process_port(port)

        # split sourceservice on commas, one row per value
        source_values = [s.strip() for s in (sourceservice or "").split(",")]
        source_values = [s for s in source_values if s] or [sourceservice]

        for source_value in source_values:

            # split targetservice on commas, one row per value
            target_values = [s.strip() for s in (targetservice or "").split(",")]
            target_values = [s for s in target_values if s] or [targetservice]

            for target_value in target_values:
                from_role = resolve_role(source_value)
                to_role = resolve_role(target_value)

                cursor.execute(
                    """
                    INSERT INTO ports_definitions (
                        product, sourceservice, targetservice, protocol,
                        original_port, description, from_role, to_role, ports
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product,
                        source_value,
                        target_value,
                        protocol,
                        port,
                        description,
                        from_role,
                        to_role,
                        ports,
                    ),
                )
                inserted += 1

    db_conn.commit()
    cursor.close()
    eprint.eprint(f"[DB] Inserted {inserted} rows into 'ports_definitions'.")


def populate_custom_ports_definitions(db_conn, custom_ports_definitions_file):
    """
    Populates the ports_definitions table from a custom port definitions CSV file.
    """

    cur = db_conn.cursor()

    with open(custom_ports_definitions_file, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        rows = [tuple(row) for row in reader if row]  # skip empty lines

    cur.executemany(
        """
        INSERT INTO ports_definitions (
            product, sourceservice, targetservice, protocol,
            original_port, description, from_role, to_role, ports
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    db_conn.commit()
    eprint.eprint(f"[DB] populate_custom_ports_definitions: Inserted {len(rows)} rows.")

    cur.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    """
    Main function.
    """

    args = get_cli_arguments()

    db_file = args.dbfilename
    role_propagations_file = str(Path(db_file).with_suffix(".csv"))
    custom_ports_definitions_file = str(Path(db_file).with_suffix(".ports"))

    try:
        db_conn = opendb(db_file)
        create_tables(db_conn)
        populate_role_propagations(db_conn, role_propagations_file)
        populate_ports_definitions(db_conn)
        populate_custom_ports_definitions(db_conn, custom_ports_definitions_file)
        db_conn.close()

        eprint.eprint("[OK] Database initialized successfully.")

    except FileNotFoundError as err:
        eprint.eprint(f"[ERROR] {err}")
        sys.exit(1)
    except RuntimeError as err:
        eprint.eprint(f"[ERROR] {err}")
        sys.exit(1)
    except sqlite3.OperationalError as err:
        eprint.eprint(f"[ERROR] Database error: {err}")
        sys.exit(1)
    except Exception as err:  # pylint: disable=broad-except
        eprint.eprint(f"[ERROR] Unexpected error: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
