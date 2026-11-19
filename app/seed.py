"""Load the UK generic foods (CoFID) into the database the first time the app starts."""

import csv
from pathlib import Path

from sqlmodel import Session, select

from app.models import Food
from app.nutrition import MAX_KCAL_100G, to_float

COFID_CSV = Path(__file__).parent / "data" / "cofid.csv"
NUTRIENTS = ("kcal", "protein", "carbs", "fat", "fibre", "sugar", "salt")


def seed_cofid(session: Session, path: Path = COFID_CSV) -> int:
    """Insert every CoFID food once. Returns how many were added (0 if already done)."""
    if not path.exists():
        return 0
    if session.exec(select(Food.id).where(Food.source == "cofid")).first() is not None:
        return 0
    added = 0
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            v = {k: to_float(row.get(k)) for k in NUTRIENTS}
            session.add(Food(
                name=row["name"].strip(),
                source="cofid",
                kcal_100g=v["kcal"], protein_100g=v["protein"], carbs_100g=v["carbs"], fat_100g=v["fat"],
                fibre_100g=v["fibre"], sugar_100g=v["sugar"], salt_100g=v["salt"],
                # CoFID gives carbs as monosaccharide equivalents, so pure sugar is ~105 g/100 g.
                # That's correct, not an error, so only the calorie check applies here.
                suspicious=v["kcal"] is not None and v["kcal"] > MAX_KCAL_100G,
                raw_data={"cofid_code": row["code"]},
            ))
            added += 1
    session.commit()
    return added
