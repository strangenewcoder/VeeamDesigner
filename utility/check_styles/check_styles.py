"""
Check style files against roles defined in the database.

The STYLES environment variable must point to the styles directory.
"""

import argparse
import os
import sqlite3
import sys

import eprint


def get_cli_arguments():
    """
    Parse and return CLI arguments.
    """

    parser = argparse.ArgumentParser(
        description="Check style files against roles defined in the database."
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


def get_roles(db_conn):
    """Return all distinct non-empty roles from ports_definitions.

    Collects both from_role and to_role columns.

    Returns:
        Sorted list of unique role strings.
    """

    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT DISTINCT from_role FROM ports_definitions WHERE from_role != ''
        UNION
        SELECT DISTINCT to_role   FROM ports_definitions WHERE to_role   != ''
    """)
    rows = cursor.fetchall()
    cursor.close()

    return sorted(role for (role,) in rows)


def get_style_files(styles_dir):
    """Return the set of base names (without .txt) from the styles directory.

    Args:
        styles_dir: path to the directory containing .txt style files.

    Returns:
        Set of role names derived from .txt filenames.

    Raises:
        FileNotFoundError: if the directory does not exist.
    """

    if not os.path.isdir(styles_dir):
        raise FileNotFoundError(f"STYLES directory not found: '{styles_dir}'")

    return {
        os.path.splitext(f)[0] for f in os.listdir(styles_dir) if f.endswith(".txt")
    }


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


def output_code_nodes(style_names):
    """
    Returns the add_node lines of the generated Python script as a list of strings.
    """

    lines = []
    auto_x = 100
    auto_y = 100
    col = 1

    for name in sorted(style_names):
        print(name)
        x_pos = str(auto_x)
        y_pos = str(auto_y)
        width = "60"
        height = "60"

        if col == 3:
            auto_x = 100
            auto_y += 150
            col = 1
        else:
            auto_x += 250
            col += 1

        style_file = f'styles_dir+"/{name}.txt"'

        lines.append(
            f"diagram.add_node("
            f'id="{name}",'
            f'label="{name}",'
            f"style={style_file},"
            f'x_pos="{x_pos}",'
            f'y_pos="{y_pos}",'
            f'width="{width}",'
            f'height="{height}")'
        )

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


def write_portfolio_script(style_names, drawing_name):
    """
    Assemble and write the generated Python script to <drawing_name>.py.
    """

    script_file = drawing_name + ".py"
    drawing_file_name = drawing_name + ".drawio"

    lines = output_code_begin()

    print("here")
    lines += output_code_nodes(style_names)

    lines += output_code_end(drawing_file_name)

    with open(script_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    eprint.eprint(f"[INFO] Script generated: {script_file}")


def main():
    """
    Main function.
    """

    args = get_cli_arguments()

    db_file = args.dbfilename

    styles_dir = os.environ.get("STYLES")
    if not styles_dir:
        eprint.eprint("[ERROR] STYLES environment variable is not set.")
        sys.exit(1)

    try:
        db_conn = opendb(db_file)
        db_roles = get_roles(db_conn)
        db_conn.close()

        style_names = get_style_files(styles_dir)

        db_role_set = set(db_roles)

        missing = sorted(db_role_set - style_names)  # roles in DB but no .txt file
        extra = sorted(style_names - db_role_set)  # .txt files with no DB role

        eprint.eprint(f"\n[INFO] Roles in DB       : {len(db_role_set)}")
        eprint.eprint(f"[INFO] Style files found : {len(style_names)}")

        if not missing and not extra:
            eprint.eprint(
                "\n[OK] All roles have a matching style file. No extra files found."
            )
            # Write script to generate Draw.io
            write_portfolio_script(style_names, "portfolio")
            return

        if missing:
            eprint.eprint(f"\n[MISSING] {len(missing)} role(s) have no style file:")
            for role in missing:
                eprint.eprint(f"  - {role}  →  expected: {styles_dir}/{role}.txt")

        if extra:
            eprint.eprint(
                f"\n[EXTRA] {len(extra)} style file(s) have no matching role:"
            )
            for name in extra:
                eprint.eprint(f"  - {name}.txt")

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
