"""End-to-end tests through the real web app. Runs in GitHub Actions before every build."""

import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp()  # throwaway database
os.environ["DEV_MODE"] = "1"

import pytest  # noqa: E402

pytest.importorskip("fastapi")
pytest.importorskip("sqlmodel")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # "with" runs startup, which creates the tables
        yield c


def test_health(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_today_page(client):
    r = client.get("/today")
    assert r.status_code == 200
    assert "Breakfast" in r.text and "Snacks" in r.text


def test_create_log_and_delete(client):
    r = client.post("/food/new", data={"name": "Test toast", "kcal_100g": "250", "protein_100g": "9",
                                       "serving_g": "40", "meal_id": "1"}, follow_redirects=False)
    assert r.status_code == 303
    location = r.headers["location"]
    food_id = int(location.split("/food/")[1].split("?")[0])
    assert "Test toast" in client.get(location).text

    r = client.post("/log", data={"food_id": str(food_id), "amount": "80", "unit": "g", "meal_id": "1"},
                    follow_redirects=False)
    assert r.status_code == 303
    day = client.get("/api/day").json()
    assert day["eaten"] == 200  # 250 kcal/100 g x 80 g

    entry_id = day["meals"][0]["entries"][0]["id"]
    client.post(f"/log/{entry_id}/delete")
    assert client.get("/api/day").json()["eaten"] == 0


def test_search(client):
    results = client.get("/api/foods/search", params={"q": "toast"}).json()
    assert results[0]["name"] == "Test toast"


def test_rejects_bad_barcode(client):
    r = client.get("/barcode", params={"code": "../etc"}, follow_redirects=False)
    assert r.status_code == 303 and "error=" in r.headers["location"]


def test_rejects_impossible_food(client):
    r = client.post("/food/new", data={"name": "Bad", "kcal_100g": "8159"})
    assert r.status_code == 200 and "Check the label" in r.text


def test_fails_closed_without_login(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "dev_mode", False)
    assert client.get("/today").status_code == 401
    r = client.get("/today", headers={"Cf-Access-Authenticated-User-Email": "friend@example.com"})
    assert r.status_code == 200
