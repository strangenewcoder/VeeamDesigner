"""
Create Veeam Design Diagram & Firewall configurations (POC).
"""

import argparse
import csv
from collections import defaultdict
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import eprint


def get_cli_arguments():
    """
    Parse and return CLI arguments.
    """

    parser = argparse.ArgumentParser(
        description="Create Veeam Design Diagram & Firewall configurations (POC)."
    )
    parser.add_argument(
        "-p",
        "--project",
        required=True,
        help="Project name (used as DB and .vd filename).",
    )
    parser.add_argument(
        "-w", "--drawing", required=True, help="Drawing name to process."
    )
    parser.add_argument(
        "-o",
        "--drawio",
        default=True,
        action="store_true",
        help="Enable Draw.io output.",
    )
    parser.add_argument(
        "-f",
        "--firewall",
        default=False,
        action="store_true",
        help="Enable firewall rules output.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        default=False,
        action="store_true",
        help="Enable debug output.",
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


def propagate_system_roles(conn):
    """
    Propagate system roles using propagation_rules.
    """
    
    cur = conn.cursor()

    # Get all propagation rules: master_role -> added_role
    cur.execute("SELECT master_role, added_role FROM role_propagation")
    propagation_rules = cur.fetchall()

    if propagation_rules:

        # Snapshot current systems rows (so we don't loop over what we're about to insert)
        cur.execute("SELECT drawings, name, ip, role, mainrole FROM systems")
        original_rows = cur.fetchall()

        new_rows = []
        for drawings, name, ip, role, mainrole in original_rows:         
            for master_role, added_role in propagation_rules:
                if role == master_role:
                    new_rows.append((drawings, name, "", added_role, 0))
        
        if new_rows:
            cur.executemany(
                "INSERT INTO systems (drawings, name, ip, role, mainrole) VALUES (?, ?, ?, ?, ?)",
                new_rows,
            )
            conn.commit()

    cur.close()


def loadsystems(file_name, drawing_name, db_conn):
    """
    Load systems from .vd file into the systems table,
    then rebuild the mappings table from the loaded systems.
    """

    cursor = db_conn.cursor()
    cursor.execute("DELETE FROM systems;")

    rows_loaded = 0
    with open(file_name, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(";")
            if len(parts) != 5:
                eprint.eprint(
                    f"[WARN] Line {line_num} skipped (expected 5 fields, got {len(parts)}): {line}"
                )
                continue

            drawings, name, ip, role, mainrole = parts
            if drawing_name in drawings:
                cursor.execute(
                    """
                    INSERT INTO systems (drawings, name, ip, role, mainrole)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (drawings, name, ip if ip else None, role, int(mainrole)),
                )
                rows_loaded += 1

    # loading the mappings
    cursor.execute("DELETE FROM mappings;")
    cursor.execute("""
        INSERT INTO mappings (from_name, from_role, to_name, to_role)
        SELECT DISTINCT
            s_from.name AS from_name,
            s_from.role AS from_role,
            s_to.name   AS to_name,
            s_to.role   AS to_role
        FROM systems s_from
        JOIN ports_definitions p ON s_from.role = p.from_role
        JOIN systems s_to        ON s_to.role   = p.to_role
        WHERE s_from.name != s_to.name
    """)

    db_conn.commit()

    eprint.eprint(f"[INFO] Loaded {rows_loaded} rows for drawing '{drawing_name}'.")


def remove_excepted_mappings(db_conn, exceptions_file_name):
    """
    Remove excepted mappings
    """
    
    if not os.path.exists(exceptions_file_name):
        eprint.eprint(f"[INFO] {exceptions_file_name} not found, skipping.")
        return
        
    cur = db_conn.cursor()
    
    with open(exceptions_file_name, newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        exceptions = [tuple(row) for row in reader if row]
        
    eprint.eprint(f"[INFO] Loaded {len(exceptions)} exceptions from {exceptions_file_name}.")

    if not exceptions:
        return

    total_deleted = 0
    for name_a, name_b in exceptions:
        cur.execute(
            """
            DELETE FROM mappings
            WHERE (from_name = ? AND to_name = ?)
               OR (from_name = ? AND to_name = ?)
            """,
            (name_a, name_b, name_b, name_a)
        )
        total_deleted += cur.rowcount
        
    eprint.eprint(f"[INFO] Removed {total_deleted} exceptions.")
        
    db_conn.commit()
    
    cur.close()


def read_drawio(file_name):
    """
    Returns a dictionary keyed by object id: {id: (label, x, y, width, height)}
    """

    result = {}

    if not os.path.exists(file_name):
        return result

    tree = ET.parse(file_name)
    root = tree.getroot()

    for obj in root.findall(".//object"):
        obj_id = obj.get("id")
        if not obj_id:
            continue

        geo = obj.find(".//mxGeometry")
        if geo is None:
            continue

        tmp_width = geo.get("width")
        tmp_height = geo.get("height")
        if not tmp_width or not tmp_height:
            continue

        # strip HTML from label
        soup = BeautifulSoup(obj.get("label", ""), "html.parser")
        obj_label = soup.text

        # truncate floats to int
        coord_x = geo.get("x", "0").split(".")[0]
        coord_y = geo.get("y", "0").split(".")[0]
        width = tmp_width.split(".")[0]
        height = tmp_height.split(".")[0]

        # obj_cell = obj.find(".//mxCell")
        # style = obj_cell.get("style") if obj_cell is not None else ""

        result[obj_id] = (obj_label, coord_x, coord_y, width, height)

        eprint.debug_eprint(
            f"[DEBUG] id={obj_id} label={obj_label} x={coord_x} y={coord_y} w={width} h={height}"
        )

    return result


def get_objs(db_conn):
    """
    Returns a list of systems with their main role and secondary roles.
    Each row: (name, ip, main_role, other_roles)
    """

    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT
            s_main.name,
            s_main.ip,
            s_main.role                     AS main_role,
            GROUP_CONCAT(s_other.role, ',') AS other_roles
        FROM systems s_main
        LEFT JOIN systems s_other
            ON  s_other.name     = s_main.name
            AND s_other.mainrole = 0
        WHERE s_main.mainrole = 1
        GROUP BY s_main.name, s_main.ip, s_main.role
    """)
    data = cursor.fetchall()
    cursor.close()

    eprint.debug_eprint(f"[DEBUG] {data}")

    return data


def get_links(db_conn):
    """
    Returns a deduplicated, sorted list of directed links between systems.
    Each row: (from_system, to_system, ports)
    """

    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT
            m.from_name AS from_system,
            m.to_name   AS to_system,
            p.ports
        FROM mappings m
        JOIN ports_definitions p
            ON m.from_role = p.from_role
            AND m.to_role   = p.to_role
    """)
           
    rows = cursor.fetchall()
    cursor.close()

    link_ports = defaultdict(set)
    for from_system, to_system, ports in rows:
        # split "445, 135" into individual ports before adding to set
        for port in ports.split(","):
            link_ports[(from_system, to_system)].add(port.strip())

    def sort_ports(port_set):
        singles = sorted(
            [p for p in port_set if " to " not in p],
            key=lambda p: int(p.replace(" ", "").split(",")[0]),
        )
        ranges = sorted(
            [p for p in port_set if " to " in p],
            key=lambda p: int(p.split(" to ")[0].strip()),
        )
        return ", ".join(singles + ranges)

    return [
        (from_system, to_system, sort_ports(port_set))
        for (from_system, to_system), port_set in link_ports.items()
    ]


def get_links_2(db_conn):
    """
    Returns a deduplicated, sorted list of directed links between systems.
    Each row: (from_system, from_ip, to_system, to_ip, ports)
    Each port/range is individually suffixed with its protocol(s) when not just TCP,
    e.g. "111 (TCP, UDP), 1058 to 2058 (TCP, UDP), 443".
    """

    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT
            m.from_name AS from_system,
            s_from.ip   AS from_ip,
            m.to_name   AS to_system,
            s_to.ip     AS to_ip,
            p.ports,
            p.protocol
        FROM mappings m
        JOIN ports_definitions p
            ON m.from_role = p.from_role
            AND m.to_role   = p.to_role
        JOIN systems s_from
            ON s_from.name = m.from_name
            AND s_from.mainrole = 1
        JOIN systems s_to
            ON s_to.name = m.to_name
            AND s_to.mainrole = 1
    """)

    rows = cursor.fetchall()
    cursor.close()

    # key: (from_system, from_ip, to_system, to_ip) -> { port_str: set(protocols) }
    link_ports = defaultdict(lambda: defaultdict(set))
    for from_system, from_ip, to_system, to_ip, ports, protocol in rows:
        protocol = (protocol or "TCP").strip().upper()
        for port in ports.split(","):
            port = port.strip()
            link_ports[(from_system, from_ip, to_system, to_ip)][port].add(protocol)

    def sort_key_single(p):
        return int(p.replace(" ", "").split(",")[0])

    def sort_key_range(p):
        return int(p.split(" to ")[0].strip())

    def format_port(port, protocols):
        if protocols == {"TCP"}:
            return port
        ordered = sorted(protocols, key=lambda x: (x != "TCP", x))
        return f"{port} ({', '.join(ordered)})"

    result = []
    for (from_system, from_ip, to_system, to_ip), port_map in link_ports.items():
        singles = sorted(
            [p for p in port_map if " to " not in p],
            key=sort_key_single,
        )
        ranges = sorted(
            [p for p in port_map if " to " in p],
            key=sort_key_range,
        )
        ordered_ports = singles + ranges

        formatted = ", ".join(format_port(p, port_map[p]) for p in ordered_ports)
        result.append((from_system, from_ip, to_system, to_ip, formatted))

    return result
    
def output_code_begin():
    """
    Returns the header lines of the generated Python script as a list of strings.
    """

    lines = []
    lines.append("import os")
    lines.append("")
    lines.append("from N2G import drawio_diagram")
    lines.append("")
    lines.append("styles_dir = os.environ.get('STYLES')")
    lines.append("")
    lines.append("diagram = drawio_diagram()")
    lines.append('diagram.add_diagram("Page-1")')

    return lines


def output_code_nodes(db_obj_data, drawing_content):
    """
    Returns the add_node lines of the generated Python script as a list of strings.
    """

    lines = []
    auto_x = 300
    auto_y = 300

    for name, ip, main_role, other_roles in db_obj_data:

        if name in drawing_content:
            _, x_pos, y_pos, width, height = drawing_content[name]
            eprint.debug_eprint(
                f"[DEBUG] {name} found in drawing at x={x_pos} y={y_pos}"
            )
        else:
            x_pos = str(auto_x)
            y_pos = str(auto_y)
            width = "60"
            height = "60"
            auto_x += 100
            auto_y += 100
            eprint.debug_eprint(
                f"[DEBUG] {name} not found, auto-positioned at x={x_pos} y={y_pos}"
            )

        style_file = f'styles_dir+"/{main_role}.txt"'

        lines.append(
            f"diagram.add_node("
            f'id="{name}",'
            f'label="{name}",'
            f"style={style_file},"
            f'x_pos="{x_pos}",'
            f'y_pos="{y_pos}",'
            f'width="{width}",'
            f'height="{height}",'
            f'data={{"ip": "{ip or ""}","role":"{main_role}","other_roles":"{other_roles or ""}"}})'
        )

        eprint.debug_eprint(f"[DEBUG] node line added: {name} role={main_role}")

    return lines


def output_code_links(link_data):
    """
    Returns the add_link lines of the generated Python script as a list of strings.
    """

    link_index = {(from_sys, to_sys): ports for from_sys, to_sys, ports in link_data}

    lines = []
    visited = set()

    for from_sys, to_sys, ports in link_data:
        if (from_sys, to_sys) in visited:
            continue

        reverse_ports = link_index.get((to_sys, from_sys), "")

        kwargs = []
        if reverse_ports:
            kwargs.append(f'src_label="{reverse_ports}"')
        if ports:
            kwargs.append(f'trgt_label="{ports}"')

        kwargs_str = ",".join(kwargs)
        lines.append(f'diagram.add_link("{from_sys}","{to_sys}",{kwargs_str})')

        visited.add((from_sys, to_sys))
        visited.add((to_sys, from_sys))

    return lines


def output_code_end(drawing_file_name):
    """
    Returns the footer lines of the generated Python script as a list of strings.
    """

    folder = os.path.dirname(drawing_file_name) or "./"
    filename = os.path.basename(drawing_file_name)
    lines = []
    lines.append(f'diagram.dump_file(filename="{filename}", folder="{folder}")')
    lines.append("")

    return lines


def write_script(
    drawing_name, drawing_file_name, drawing_content, db_obj_data, links_data
):
    """
    Assemble and write the generated Python script to <drawing_name>.py.
    """

    script_file = drawing_name + ".py"

    lines = output_code_begin()
    lines += output_code_nodes(db_obj_data, drawing_content)
    lines += output_code_links(links_data)
    lines += output_code_end(drawing_file_name)

    with open(script_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    eprint.eprint(f"[INFO] Script generated: {script_file}")


def output_firewall(links_data):
    """
    One firewall rule per directed pair, ports already deduplicated and sorted.
    """

    lines = []
    for from_sys, to_sys, ports in links_data:
        lines.append(f'"{from_sys}", "{to_sys}", "{ports}"')
    return lines


def output_firewall_2(links_data):
    """
    One firewall rule per directed pair, ports already deduplicated and sorted.
    """

    lines = []
    for from_sys, from_ip, to_sys, to_ip, ports in links_data:
        lines.append(f'"{from_sys}", "{from_ip}", "{to_sys}", "{to_ip}", "{ports}"')
    return lines 
    
def main():
    """
    Main function.
    """

    args = get_cli_arguments()

    project_name = args.project
    drawing_name = args.drawing
    drawio_output = args.drawio
    firewall_output = args.firewall

    eprint.set_debug(args.debug)

    if firewall_output:
        drawio_output = False

    eprint.eprint(f"[INFO] Project         : {project_name}")
    eprint.eprint(f"[INFO] Drawing         : {drawing_name}")
    eprint.eprint(f"[INFO] Drawio_output   : {drawio_output}")
    eprint.eprint(f"[INFO] Firewall_output : {firewall_output}")

    db_file_name = project_name + ".db"
    systems_file_name = project_name + ".vd"
    exceptions_file_name = drawing_name + ".exc"
    drawing_file_name = drawing_name + ".drawio"

    try:
        db_conn = opendb(db_file_name)
        # Read the systems file
        loadsystems(systems_file_name, drawing_name, db_conn)
        # Propagate system roles
        propagate_system_roles(db_conn)
        # Remove exceptions
        remove_excepted_mappings(db_conn, exceptions_file_name)   
        # Read the drawio.file
        drawing_content = read_drawio(drawing_file_name)
        # Read obj data from db
        db_obj_data = get_objs(db_conn)
        # Read links data from db
        links_data = get_links(db_conn)
        links_data_2 = get_links_2(db_conn)
        if drawio_output:
            # Write script to generate Draw.io
            write_script(
                drawing_name,
                drawing_file_name,
                drawing_content,
                db_obj_data,
                links_data,
            )
        else:
            # Generate firewall rule list
            for line in output_firewall(links_data):
                print(line)
                
            print ()
            
            for line in output_firewall_2(links_data_2):
                print(line)

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
