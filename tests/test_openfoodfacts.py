from app.sources.openfoodfacts import is_valid_barcode, map_product

NUTELLA = {
    "code": "3017620422003",
    "status": 1,
    "product": {
        "product_name": "Nutella",
        "brands": "Ferrero,Nutella",
        "serving_size": "15 g",
        "serving_quantity": 15,
        "nutriments": {
            "energy-kcal_100g": 539,
            "energy-kj_100g": 2252,
            "fat_100g": 30.9,
            "carbohydrates_100g": 57.5,
            "sugars_100g": 56.3,
            "proteins_100g": 6.3,
            "salt_100g": 0.107,
        },
    },
}

MESSY_BISCUIT = {
    "status": 1,
    "product": {
        "product_name": "Choc biscuits",
        "serving_size": "2 biscuits (25g)",
        "nutriments": {"energy_100g": 1950, "fat_100g": "20"},
    },
}


def test_maps_nutella():
    food = map_product("3017620422003", NUTELLA)
    assert food["name"] == "Nutella"
    assert food["brand"] == "Ferrero"
    assert food["kcal_100g"] == 539
    assert food["fibre_100g"] is None  # unknown, not 0
    assert food["serving_g"] == 15
    assert food["units"] == [{"name": "serving", "grams": 15}]
    assert not food["suspicious"]
    assert food["raw_data"] is NUTELLA


def test_maps_messy_biscuit():
    food = map_product("123456", MESSY_BISCUIT)
    assert food["kcal_100g"] == 466.1  # converted from kJ
    assert food["fat_100g"] == 20
    assert food["protein_100g"] is None
    assert food["serving_g"] == 25
    assert {"name": "biscuit", "grams": 12.5} in food["units"]


def test_not_found():
    assert map_product("000000", {"status": 0}) is None
    assert map_product("000000", None) is None


def test_barcode_validation():
    assert is_valid_barcode("3017620422003")
    assert not is_valid_barcode("12")
    assert not is_valid_barcode("12345/../x")
    assert not is_valid_barcode("")
