import sys


def load_pairs(pairs_path):
    with open(pairs_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()  # handles \r\n and \n, strips line endings

    # Strip trailing/leading whitespace (tabs, spaces) picked up from copy-paste,
    # but keep the line as-is otherwise.
    lines = [line.rstrip(" \t") for line in lines]

    # Drop fully blank lines (in case some exist), but keep pairing intact
    # by only dropping blanks that appear between complete pairs, not inside one.
    cleaned = [l for l in lines if l != ""]

    if len(cleaned) % 2 != 0:
        raise ValueError(
            f"Expected an even number of non-blank lines (search/replace pairs), "
            f"got {len(cleaned)}. Check the pairs file for a missing line."
        )

    pairs = []
    for i in range(0, len(cleaned), 2):
        search, replace = cleaned[i], cleaned[i + 1]
        pairs.append((search, replace))
    return pairs


def read_text_any_encoding(path):
    """Try a list of common encodings until one works, return (text, encoding_used)."""
    encodings_to_try = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    last_error = None
    for enc in encodings_to_try:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read(), enc
        except UnicodeDecodeError as e:
            last_error = e
            continue
    # latin-1 never actually fails (it maps every byte), so we should never get here,
    # but just in case:
    raise last_error


def apply_replacements(target_path, pairs, output_path):
    text, encoding_used = read_text_any_encoding(target_path)
    print(f"Detected target file encoding: {encoding_used}\n")

    counts = []
    for search, replace in pairs:
        n = text.count(search)
        text = text.replace(search, replace)
        counts.append((search, replace, n))

    # Write output as UTF-8 for consistency/portability, regardless of source encoding
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    return counts


if __name__ == "__main__":
    pairs_path = sys.argv[1]
    target_path = sys.argv[2]
    output_path = sys.argv[3]

    pairs = load_pairs(pairs_path)
    print(f"Loaded {len(pairs)} search/replace pairs.\n")

    counts = apply_replacements(target_path, pairs, output_path)

    print("Replacement report:")
    for search, replace, n in counts:
        flag = "" if n > 0 else "  <-- NOT FOUND in target file"
        print(f"  [{n:>3}x] {search!r} -> {replace!r}{flag}")

    print(f"\nDone. Output written to {output_path}")
