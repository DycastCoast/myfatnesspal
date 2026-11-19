"""Turn the UK CoFID spreadsheet into app/data/cofid.csv.

Run on your PC (not on the cluster), once per new edition of CoFID:
    pip install openpyxl
    python scripts/import_cofid.py "path\\to\\CoFID.xlsx"

Download the spreadsheet from:
    https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid

The data is under the Open Government Licence, so it's fine to commit the CSV,
as long as the app credits the source (Settings page does).
"""

import csv
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "cofid.csv"
CODE = re.compile(r"^\d+-\d+")
FIELDS = ["code", "name", "kcal", "protein", "carbs", "fat", "fibre", "sugar", "salt"]

# Which spreadsheet column feeds each field: first header that starts with one of these.
WANTED = {
    "kcal": ["Energy (kcal)"],
    "protein": ["Protein"],
    "carbs": ["Carbohydrate"],
    "fat": ["Fat"],
    "fibre": ["AOAC fibre"],  # UK labels use AOAC; NSP is a different (lower) measure, so don't mix them
    "sugar": ["Total sugars"],
}


def cell_value(value):
    """CoFID uses "Tr" for trace (~0) and "N" or blank for not measured (unknown)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.lower().startswith("tr"):
        return 0.0
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def find_header(sheet):
    for row in sheet.iter_rows(min_row=1, max_row=10, values_only=True):
        cells = [str(c).strip() if c is not None else "" for c in row]
        if "Food Name" in cells:
            return cells
    raise SystemExit(f"No 'Food Name' header in sheet {sheet.title!r}")


def column_for(header, prefixes):
    for prefix in prefixes:
        for i, name in enumerate(header):
            if name == prefix or name.startswith(prefix + " ") or name.startswith(prefix + "("):
                return i
    return None


def read_sheet(sheet, wanted):
    header = find_header(sheet)
    # The Inorganics sheet leaves the code column's header blank, so fall back to column A.
    code_i = header.index("Food Code") if "Food Code" in header else 0
    name_i = header.index("Food Name")
    cols = {field: column_for(header, prefixes) for field, prefixes in wanted.items()}
    rows = {}
    for row in sheet.iter_rows(values_only=True):
        code = str(row[code_i]).strip() if row[code_i] is not None else ""
        if not CODE.match(code):
            continue  # header, notes or blank row
        values = {f: (cell_value(row[i]) if i is not None and i < len(row) else None) for f, i in cols.items()}
        rows[code] = {"name": str(row[name_i]).strip(), **values}
    return rows


def sheet_named(book, word):
    for name in book.sheetnames:
        if word.lower() in name.lower():
            return book[name]
    return None


def main(path):
    from openpyxl import load_workbook

    book = load_workbook(path, read_only=True, data_only=True)
    proximates = sheet_named(book, "proximates")
    if proximates is None:
        raise SystemExit("Couldn't find the Proximates sheet.")
    foods = read_sheet(proximates, WANTED)

    inorganics = sheet_named(book, "inorganics")
    if inorganics is not None:
        sodium = read_sheet(inorganics, {"sodium_mg": ["Sodium"]})
        for code, food in foods.items():
            mg = sodium.get(code, {}).get("sodium_mg")
            food["salt"] = None if mg is None else round(mg * 2.5 / 1000, 2)  # salt = sodium x 2.5
    for food in foods.values():
        food.setdefault("salt", None)

    kept = 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for code, food in sorted(foods.items()):
            if food["kcal"] is None:
                continue  # a food with no calories isn't useful for counting them
            writer.writerow({"code": code, **{k: ("" if food.get(k) is None else food[k]) for k in FIELDS[1:]}})
            kept += 1
    print(f"Wrote {kept} foods to {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
