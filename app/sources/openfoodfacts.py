"""Open Food Facts: fetch a product by barcode and map it into our format.

The mapper is pure (no network) so it can be tested with saved examples.
Every food source gets its own mapper that outputs the same shape.
"""

import re

from app.nutrition import (
    is_suspicious,
    kj_to_kcal,
    parse_count_unit,
    parse_serving_grams,
    to_float,
)

BARCODE_RE = re.compile(r"^\d{6,14}$")


class SourceUnavailable(Exception):
    """The food database couldn't be reached (timeout, outage...)."""


def is_valid_barcode(code):
    # Only digits: stops anyone sneaking odd characters into the URL we build.
    return bool(code) and bool(BARCODE_RE.match(code))


def map_product(barcode, payload):
    """Turn an Open Food Facts response into our food fields, or None if not found."""
    if not payload or payload.get("status") != 1:
        return None
    product = payload.get("product") or {}
    n = product.get("nutriments") or {}

    kcal = to_float(n.get("energy-kcal_100g"))
    if kcal is None:
        kj = to_float(n.get("energy-kj_100g"))
        if kj is None:
            kj = to_float(n.get("energy_100g"))  # OFF stores this one in kJ
        kcal = kj_to_kcal(kj)
    if kcal is not None:
        kcal = round(kcal, 1)

    fields = {
        "kcal_100g": kcal,
        "protein_100g": to_float(n.get("proteins_100g")),
        "carbs_100g": to_float(n.get("carbohydrates_100g")),
        "fat_100g": to_float(n.get("fat_100g")),
        "fibre_100g": to_float(n.get("fiber_100g")),
        "sugar_100g": to_float(n.get("sugars_100g")),
        "salt_100g": to_float(n.get("salt_100g")),
    }

    serving_text = product.get("serving_size")
    serving_g = to_float(product.get("serving_quantity"))
    if not serving_g:
        serving_g = parse_serving_grams(serving_text)

    units = []
    if serving_g:
        units.append({"name": "serving", "grams": round(serving_g, 1)})
        counted = parse_count_unit(serving_text)
        if counted:
            count, unit_name = counted
            units.append({"name": unit_name, "grams": round(serving_g / count, 1)})

    name = (
        product.get("product_name_en")
        or product.get("product_name")
        or product.get("generic_name")
        or "Unnamed product"
    ).strip()
    brand = (product.get("brands") or "").split(",")[0].strip() or None

    return {
        "barcode": barcode,
        "name": name,
        "brand": brand,
        "source": "off",
        **fields,
        "serving_g": round(serving_g, 1) if serving_g else None,
        "suspicious": is_suspicious(
            fields["kcal_100g"], fields["protein_100g"], fields["carbs_100g"], fields["fat_100g"]
        ),
        "units": units,
        "raw_data": payload,
    }


async def fetch_product(barcode, timeout, contact):
    """Ask Open Food Facts for a barcode. Returns the JSON, or {"status": 0} if unknown."""
    import httpx  # imported here so the mapper tests don't need httpx

    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    headers = {"User-Agent": f"MyFatnessPal/0.1 ({contact})"}
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        raise SourceUnavailable(str(exc)) from exc
    if response.status_code == 404:
        return {"status": 0}
    if response.status_code != 200:
        raise SourceUnavailable(f"HTTP {response.status_code}")
    return response.json()
