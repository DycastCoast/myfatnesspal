import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "hello.db"
DEV_MODE = os.environ.get("DEV_MODE") == "1"

app = FastAPI()


def get_user_email(request: Request) -> str:
    """The ONE place that decides who the user is."""
    email = request.headers.get("cf-access-authenticated-user-email")
    if email:
        return email
    if DEV_MODE:
        return "dev@localhost"
    raise HTTPException(status_code=401, detail="Not logged in")


@app.get("/")
def hello(request: Request):
    email = get_user_email(request)
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS visits (email TEXT PRIMARY KEY, count INTEGER NOT NULL)"
        )
        db.execute(
            "INSERT INTO visits (email, count) VALUES (?, 1) "
            "ON CONFLICT(email) DO UPDATE SET count = count + 1",
            (email,),
        )
        (count,) = db.execute(
            "SELECT count FROM visits WHERE email = ?", (email,)
        ).fetchone()
    return {"hello": email, "your_visits": count}


@app.get("/healthz")
def health():
    return {"ok": True}