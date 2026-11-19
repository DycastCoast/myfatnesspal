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


def test_edit_food_and_recalculate_my_logs(client):
    r = client.post("/food/new", data={"name": "Edit me", "kcal_100g": "100"}, follow_redirects=False)
    food_id = int(r.headers["location"].split("/food/")[1].split("?")[0])
    client.post("/log", data={"food_id": str(food_id), "amount": "200", "unit": "g", "meal_id": "2"})
    assert client.get("/api/day").json()["eaten"] == 200

    assert client.get(f"/food/{food_id}/edit").status_code == 200
    r = client.post(f"/food/{food_id}/edit", data={"name": "Edited", "kcal_100g": "150", "update_my_logs": "1"},
                    follow_redirects=False)
    assert r.status_code == 303
    day = client.get("/api/day").json()
    assert day["eaten"] == 300
    entry = day["meals"][1]["entries"][0]
    assert entry["food_name"] == "Edited"
    client.post(f"/log/{entry['id']}/delete")


def test_edit_without_recalculating_keeps_history(client):
    r = client.post("/food/new", data={"name": "Keep me", "kcal_100g": "100"}, follow_redirects=False)
    food_id = int(r.headers["location"].split("/food/")[1].split("?")[0])
    client.post("/log", data={"food_id": str(food_id), "amount": "100", "unit": "g", "meal_id": "3"})
    client.post(f"/food/{food_id}/edit", data={"name": "Keep me", "kcal_100g": "999"})
    day = client.get("/api/day").json()
    assert day["eaten"] == 100  # snapshot: the past didn't change
    client.post(f"/log/{day['meals'][2]['entries'][0]['id']}/delete")


def test_backup_downloads_sqlite(client):
    r = client.get("/backup")
    assert r.status_code == 200
    assert r.content.startswith(b"SQLite format 3")


def test_pwa_files(client):
    assert "javascript" in client.get("/sw.js").headers["content-type"]
    assert client.get("/static/manifest.webmanifest").json()["start_url"] == "/today"
    assert client.get("/static/icons/apple-touch-icon.png").status_code == 200


def test_seed_cofid(client, tmp_path):
    from sqlmodel import Session

    from app.db import engine
    from app.seed import seed_cofid

    csv_file = tmp_path / "cofid.csv"
    csv_file.write_text("code,name,kcal,protein,carbs,fat,fibre,sugar,salt\n"
                        "13-128,\"Bananas, flesh only\",81.0,1.2,20.3,0.1,1.4,18.1,0.0\n", encoding="utf-8")
    with Session(engine) as session:
        # 1 if this is the first load; 0 if the real CoFID file was already loaded at startup
        assert seed_cofid(session, csv_file) in (0, 1)
        assert seed_cofid(session, csv_file) == 0  # only ever loads once
    results = client.get("/api/foods/search", params={"q": "banana"}).json()
    assert any(f["source"] == "cofid" for f in results)


def test_fails_closed_without_login(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "dev_mode", False)
    assert client.get("/today").status_code == 401
    friend = {"Cf-Access-Authenticated-User-Email": "friend@example.com"}
    assert client.get("/today", headers=friend).status_code == 200
    assert client.get("/backup", headers=friend).status_code == 403  # not the admin
    toast = client.get("/api/foods/search", params={"q": "toast"}, headers=friend).json()[0]
    assert client.get(f"/food/{toast['id']}/edit", headers=friend).status_code == 403  # not their food


def test_tailscale_login(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "dev_mode", False)
    monkeypatch.setattr(settings, "auth_mode", "tailscale")
    me = {"Tailscale-User-Login": "Me@Example.com"}
    assert client.get("/today", headers=me).status_code == 200
    # A Cloudflare header means nothing on the Pi
    assert client.get("/today", headers={"Cf-Access-Authenticated-User-Email": "me@example.com"}).status_code == 401


def test_allowed_logins_and_single_account(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "dev_mode", False)
    monkeypatch.setattr(settings, "auth_mode", "tailscale")
    monkeypatch.setattr(settings, "allowed_logins", {"dycastcoast@github"})
    monkeypatch.setattr(settings, "account_email", "me@example.com")
    assert client.get("/today", headers={"Tailscale-User-Login": "someone@else.com"}).status_code == 403
    assert client.get("/today", headers={"Tailscale-User-Login": "DycastCoast@github"}).status_code == 200

    from sqlmodel import Session, select
    from app.db import engine
    from app.models import User
    with Session(engine) as s:  # the github login used the existing email account, not a new one
        emails = {u.email for u in s.exec(select(User)).all()}
    assert "me@example.com" in emails and "dycastcoast@github" not in emails
