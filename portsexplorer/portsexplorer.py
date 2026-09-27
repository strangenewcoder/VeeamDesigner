"""
PortsExplorer — Flask/HTMX tool for exploring the ports_definitions table.
"""

import argparse
import os
import sqlite3

from flask import Flask, render_template, request, g

app = Flask(__name__)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def get_db():
    """Open the db."""

    if "db" not in g:
        g.db = sqlite3.connect(app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    """Close the db."""

    if e:
        print(f"Teardown due to error: {e}")
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """/ app route."""

    db = get_db()
    roles = db.execute(
        "SELECT DISTINCT from_role FROM ports_definitions WHERE from_role != '' ORDER BY from_role"
    ).fetchall()
    return render_template(
        "index.html", roles=[r["from_role"] for r in roles], swapped=False
    )


@app.route("/roles")
def roles():
    """
    /roles route — (re)populates column 1.

    Normally column 1 lists distinct `from_role` values. When `swapped=1`
    is passed, column 1 instead lists distinct `to_role` values, so the
    user can drive the exploration from the other direction.
    """

    swapped = request.args.get("swapped", "0") == "1"
    db = get_db()
    column = "to_role" if swapped else "from_role"
    # `column` is always one of the two hardcoded literals above, never
    # user input, so this is safe to interpolate into the SQL string.
    rows = db.execute(
        f"SELECT DISTINCT {column} FROM ports_definitions "
        f"WHERE {column} != '' ORDER BY {column}"
    ).fetchall()
    return render_template(
        "partials/roles.html",
        roles=[r[column] for r in rows],
        swapped=swapped,
        is_partial=True,
    )


@app.route("/to_roles")
def to_roles():
    """/to_roles route."""

    from_role = request.args.get("from_role", "")
    swapped = request.args.get("swapped", "0") == "1"
    db = get_db()

    if swapped:
        # Column 1 held `to_role` values, so look up the related
        # `from_role` values for column 2.
        rows = db.execute(
            """
            SELECT DISTINCT from_role FROM ports_definitions
            WHERE to_role = ? AND from_role != ''
            ORDER BY from_role
            """,
            (from_role,),
        ).fetchall()
        values = [r["from_role"] for r in rows]
    else:
        rows = db.execute(
            """
            SELECT DISTINCT to_role FROM ports_definitions
            WHERE from_role = ? AND to_role != ''
            ORDER BY to_role
            """,
            (from_role,),
        ).fetchall()
        values = [r["to_role"] for r in rows]

    return render_template(
        "partials/to_roles.html",
        to_roles=values,
        from_role=from_role,
    )


@app.route("/ports")
def ports():
    """/ports route."""

    from_role = request.args.get("from_role", "")
    to_role = request.args.get("to_role", "")
    db = get_db()

    # Direct: from_role → to_role
    direct = db.execute(
        """
        SELECT DISTINCT ports FROM ports_definitions
        WHERE from_role = ? AND to_role = ? AND ports != ''
        ORDER BY ports
        """,
        (from_role, to_role),
    ).fetchall()

    # Reverse: to_role → from_role
    reverse = db.execute(
        """
        SELECT DISTINCT ports FROM ports_definitions
        WHERE from_role = ? AND to_role = ? AND ports != ''
        ORDER BY ports
        """,
        (to_role, from_role),
    ).fetchall()

    port_entries = []
    for r in direct:
        port_entries.append({"ports": r["ports"], "direction": "direct"})
    for r in reverse:
        port_entries.append({"ports": r["ports"], "direction": "reverse"})

    return render_template(
        "partials/ports.html",
        port_entries=port_entries,
        from_role=from_role,
        to_role=to_role,
    )


@app.route("/descriptions")
def descriptions():
    """/descriptions route."""

    from_role = request.args.get("from_role", "")
    to_role = request.args.get("to_role", "")
    selected_ports = request.args.get("ports", "")
    direction = request.args.get("direction", "direct")
    db = get_db()

    if direction == "direct":
        q_from, q_to = from_role, to_role
    else:
        q_from, q_to = to_role, from_role

    rows = db.execute(
        """
        SELECT product, sourceservice, targetservice, protocol,
               original_port, description, from_role, to_role, ports
        FROM ports_definitions
        WHERE from_role = ? AND to_role = ? AND ports = ?
        ORDER BY product, sourceservice
        """,
        (q_from, q_to, selected_ports),
    ).fetchall()

    return render_template(
        "partials/descriptions.html",
        rows=rows,
        from_role=from_role,
        to_role=to_role,
        ports=selected_ports,
        direction=direction,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    """
    Main function.
    """

    parser = argparse.ArgumentParser(description="Ports explorer web UI")
    parser.add_argument(
        "-f",
        "--dbfilename",
        required=True,
        help="Database file name.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5000, type=int)
    args = parser.parse_args()

    app.config["DB_PATH"] = args.dbfilename
    if not os.path.exists(app.config["DB_PATH"]):
        print(f"[ERROR] Database not found: {app.config["DB_PATH"]}")
        raise SystemExit(1)

    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
