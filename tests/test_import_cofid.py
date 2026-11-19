import csv
import importlib.util
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "import_cofid.py"


def load_script(tmp_path):
    spec = importlib.util.spec_from_file_location("import_cofid", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = tmp_path / "cofid.csv"
    return module


def fake_cofid(path):
    """A tiny workbook shaped like the real one: notes rows, then headers, then data."""
    book = openpyxl.Workbook()
    prox = book.active
    prox.title = "1.3 Proximates"
    prox.append(["McCance and Widdowson's notes row"])
    prox.append(["Food Code", "Food Name", "Description", "Protein (g)", "Fat (g)", "Carbohydrate (g)",
                 "Energy (kcal) (kcal)", "Energy (kJ) (kJ)", "Total sugars (g)", "AOAC fibre (g)", "Fatty acids, total saturated (g)"])
    prox.append(["13-128", "Bananas, flesh only", "", "1.2", "0.1", "20.3", "81", "343", "18.1", "1.4", "Tr"])  # numbers stored as text
    prox.append(["11-433", "Chicken, breast, grilled", "", 32.0, "Tr", 0, 148, 626, 0, "N", 0.6])
    prox.append(["99-999", "Mystery food", "", None, None, None, None, None, None, None, None])
    inorg = book.create_sheet("1.4 Inorganics")
    inorg.append([" ", "Food Name", "Sodium (mg)", "Potassium (mg)"])  # real file has a blank code header
    inorg.append(["13-128", "Bananas, flesh only", 1, 330])
    inorg.append(["11-433", "Chicken, breast, grilled", 80, 400])
    book.save(path)


def test_converts_cofid(tmp_path):
    xlsx = tmp_path / "cofid.xlsx"
    fake_cofid(xlsx)
    module = load_script(tmp_path)
    module.main(str(xlsx))
    rows = list(csv.DictReader(open(module.OUT, encoding="utf-8")))
    assert [r["code"] for r in rows] == ["11-433", "13-128"]  # no-calorie food dropped
    chicken = rows[0]
    assert chicken["fat"] == "0.0"  # "Tr" = trace
    assert chicken["fibre"] == ""  # "N" = unknown, not 0
    assert chicken["salt"] == "0.2"  # 80 mg sodium x 2.5
    banana = rows[1]
    assert banana["kcal"] == "81.0" and banana["sugar"] == "18.1" and banana["fibre"] == "1.4"
