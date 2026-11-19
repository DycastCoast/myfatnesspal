"""Pure nutrition maths. No web or database imports, so it's easy to test."""

import math
import re

KJ_PER_KCAL = 4.184
# Pure fat is ~900 kcal/100 g, so anything above that is a data error.
MAX_KCAL_100G = 900
NUTRIENTS = ("kcal", "protein", "carbs", "fat")


def to_float(value):
    """Turn messy input ("12,5", "7", 3, None, "abc") into a float or None.

    None means *unknown*. We never turn unknown into 0.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(",", ".")
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    if math.isnan(number) or math.isinf(number) or number < 0:
        return None
    return number


def kj_to_kcal(kj):
    return None if kj is None else kj / KJ_PER_KCAL


def scale(per_100g, grams):
    """Scale per-100 g values to an amount. Unknown stays unknown."""
    factor = grams / 100
    return {
        key: (None if value is None else round(value * factor, 1))
        for key, value in per_100g.items()
    }


def sum_known(values):
    """Add up the known values. Returns (total, complete?)."""
    values = list(values)
    known = [v for v in values if v is not None]
    return round(sum(known), 1), len(known) == len(values)


def is_suspicious(kcal, protein=None, carbs=None, fat=None):
    """Flag per-100 g numbers that can't be right."""
    if kcal is not None and kcal > MAX_KCAL_100G:
        return True
    macros = [m for m in (protein, carbs, fat) if m is not None]
    if any(m > 100 for m in macros):
        return True
    return sum(macros) > 100.5  # allow for rounding on labels


_GRAMS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(g|ml)\b", re.IGNORECASE)
_COUNT = re.compile(r"^\s*(\d+)\s+([a-z][a-z ]*?)\s*\(", re.IGNORECASE)


def parse_serving_grams(text):
    """"15 g" -> 15.0, "2 biscuits (25g)" -> 25.0, "a bowl" -> None.

    ml is treated as grams: close enough for most drinks.
    """
    if not text:
        return None
    matches = _GRAMS.findall(str(text))
    if not matches:
        return None
    return to_float(matches[-1][0])


def parse_count_unit(text):
    """"2 biscuits (25g)" -> (2, "biscuit"). Anything else -> None."""
    if not text:
        return None
    match = _COUNT.match(str(text))
    if not match:
        return None
    count = int(match.group(1))
    name = match.group(2).strip().lower()
    if count <= 0 or not name:
        return None
    if name.endswith("s") and not name.endswith("ss"):
        name = name[:-1]
    return count, name
