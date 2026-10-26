"""
Parse HTML saved from Veeam Web Site, getting TCP/IP port usage.
"""

import argparse
import re

from bs4 import BeautifulSoup


def get_cli_arguments():
    """
    Parse and return CLI arguments.
    """

    parser = argparse.ArgumentParser(
        description="Parse HTML saved from Veeam Web Site, getting TCP/IP port usage."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input HTML file path.",
    )
    parser.add_argument(
        "-p",
        "--product",
        required=True,
        help="Product code (e.g. VBR).",
    )

    return parser.parse_args()


def fix_mojibake(text):
    """
    Normalize special characters in extracted text.
    """

    replacements = {
        "\u2014": "-",  # em dash (unicode)
        "\u00a0": " ",  # non-breaking space
    }

    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    return text


def normalize_table_rows(rows):
    """
    Reconstruct incomplete rows by carrying forward values from previous rows.
    """

    normalized_rows = []
    last_from = ""
    last_to = ""
    last_protocol = ""
    last_desc = ""

    for row in rows:
        # Skip rows that are clearly not data
        if len(row) == 0:
            continue

        # Skip header row if it contains known labels
        header_keywords = {"from", "to", "protocol", "port", "notes"}
        row_lower = [cell.strip().lower() for cell in row]
        if any(h in header_keywords for h in row_lower):
            continue

        # Reconstruct based on length
        if len(row) == 5:
            last_from = row[0].strip()
            last_to = row[1].strip()
            last_protocol = row[2].strip()
            last_desc = row[4].strip()
            normalized_rows.append(row)
        elif len(row) == 4:
            last_to = row[0].strip()
            last_protocol = row[1].strip()
            last_desc = row[3].strip()
            normalized_rows.append([last_from] + row)
        elif len(row) == 3:
            last_protocol = row[0].strip()
            last_desc = row[2].strip()
            normalized_rows.append([last_from, last_to] + row)
        elif len(row) == 2:
            desc = row[1].strip()
            if len(desc) > 10:
                normalized_rows.append([last_from, last_to, last_protocol] + row)
            else:
                normalized_rows.append([last_from, last_to] + row + [last_desc])

    return normalized_rows


def extract_port_tables(html_path):
    """
    Parse an HTML file and extract all tables as a list of rows.
    """

    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    results = []

    # Find all tables
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            row = [cell.get_text(separator=" ", strip=True) for cell in cells]
            if row:
                rows.append(row)
        results.append(rows)

    return results


def main():
    """
    Main function.
    """

    args = get_cli_arguments()
    input_html = args.input
    product_code = args.product

    # Extract tables
    tables = extract_port_tables(input_html)

    # Final flat output list
    final_rows = []

    # Normalize tables
    for table in tables:
        normalized = normalize_table_rows(table)
        for row in normalized:
            final_rows.append([product_code] + row)

    # Print CSV-style output
    print("product;sourceService;targetService;protocol;port;description")
    for row in final_rows:
        # Clean encoded chars from the last column (description)
        cleaned_row = [fix_mojibake(col) for col in row]

        # Remove space before final dot (if any) in description
        if cleaned_row[-1]:
            cleaned_row[-1] = re.sub(r"\s+\.$", ".", cleaned_row[-1])

            # Remove starting and ending double quotes if present
            if cleaned_row[-1].startswith('"') and cleaned_row[-1].endswith('"'):
                cleaned_row[-1] = cleaned_row[-1][1:-1]

        print(";".join(cleaned_row))


if __name__ == "__main__":
    main()
