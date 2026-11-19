"""Routes: turn web requests into service calls, and results into pages or JSON."""

from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app import nutrition, services
from app.auth import get_current_user
from app.db import get_session, init_db
from app.models import Food, User
from app.sources.openfoodfacts import SourceUnavailable, is_valid_barcode

BASE = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="MyFatnessPal", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
templates.env.filters["num"] = lambda n: "—" if n is None else f"{round(n):,}"
templates.env.globals["meal_icons"] = {
    "breakfast": "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
    "lunch": "M12 4a8 8 0 1 0 0 16a8 8 0 1 0 0-16zM12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8z",
    "dinner": "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
    "snacks": "M12 8c-2.5-2.5-8-1.5-8 3.5C4 16 7.5 21 12 21s8-5 8-9.5c0-5-5.5-6-8-3.5zM12 8c0-2 1-4 3-5",
    "accent": "M12 5v14M5 12h14",
}
templates.env.filters["dec"] = lambda n: "Unknown" if n is None else f"{n:g}"

CurrentUser = Depends(get_current_user)
DB = Depends(get_session)


def as_int(value):
    """Query strings can arrive as "" or junk: treat those as missing."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_day(value):
    try:
        return date.fromisoformat(value) if value else services.today()
    except ValueError:
        return services.today()


def render(request: Request, name: str, user: User, **context):
    return templates.TemplateResponse(request, name, {"user": user, "today": services.today(), **context})


def go(url: str):
    return RedirectResponse(url, status_code=303)  # 303 = "now GET this page" after a form POST


def day_label(day: date):
    t = services.today()
    if day == t:
        return "Today"
    if day == t - timedelta(days=1):
        return "Yesterday"
    if day == t + timedelta(days=1):
        return "Tomorrow"
    return day.strftime("%A")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def home():
    return go("/today")


@app.get("/today")
def today_page(request: Request, d: str | None = None, user: User = CurrentUser, session: Session = DB):
    day = parse_day(d)
    return render(request, "today.html", user, s=services.day_summary(session, user, day),
                  day=day, label=day_label(day), prev=day - timedelta(days=1), next=day + timedelta(days=1),
                  nav="today")


@app.get("/add")
def add_page(request: Request, meal_id: str | None = None, d: str | None = None, q: str = "",
             error: str | None = None, user: User = CurrentUser, session: Session = DB):
    meals = services.meals_for(session, user)
    meal = services.get_meal(session, user, as_int(meal_id)) or meals[0]
    results = services.search_foods(session, user, q) if q else None
    recent = services.recent_foods(session, user) if not q else []
    return render(request, "add.html", user, meal=meal, day=parse_day(d), q=q, results=results,
                  recent=recent, error=error, nav="add")


@app.get("/barcode")
async def barcode_lookup(code: str, meal_id: str | None = None, d: str | None = None,
                         user: User = CurrentUser, session: Session = DB):
    code = code.strip()
    suffix = f"meal_id={as_int(meal_id) or ''}&d={parse_day(d).isoformat()}"
    if not is_valid_barcode(code):
        return go(f"/add?{suffix}&error=That+doesn%27t+look+like+a+barcode")
    try:
        food = await services.get_or_fetch_barcode(session, code, user)
    except SourceUnavailable:
        return go(f"/add?{suffix}&error=Couldn%27t+reach+the+food+database.+Try+again+or+create+the+food.")
    if food is None:
        return go(f"/food/new?barcode={code}&{suffix}")
    return go(f"/food/{food.id}?{suffix}")


@app.get("/food/new")
def new_food_page(request: Request, barcode: str = "", meal_id: str | None = None, d: str | None = None,
                  user: User = CurrentUser, session: Session = DB):
    return render(request, "food_new.html", user, form={"barcode": barcode}, error=None,
                  meal_id=as_int(meal_id) or "", day=parse_day(d), nav="add")


@app.post("/food/new")
async def new_food_submit(request: Request, user: User = CurrentUser, session: Session = DB):
    form = dict(await request.form())
    meal_id = as_int(form.get("meal_id")) or ""
    day = parse_day(form.get("d"))
    try:
        food = services.create_custom_food(session, user, form)
    except ValueError as exc:
        return render(request, "food_new.html", user, form=form, error=str(exc),
                      meal_id=meal_id, day=day, nav="add")
    return go(f"/food/{food.id}?meal_id={meal_id}&d={day.isoformat()}")


@app.get("/food/{food_id}")
def food_page(request: Request, food_id: int, meal_id: str | None = None, d: str | None = None,
              user: User = CurrentUser, session: Session = DB):
    food = session.get(Food, food_id)
    if food is None or not services.can_see(food, user):
        raise HTTPException(404, "Food not found")
    meals = services.meals_for(session, user)
    meal = services.get_meal(session, user, as_int(meal_id)) or meals[0]
    units = services.units_for(session, food)
    default_unit = next((u for u in units if u.name == "serving"), None)
    return render(request, "food.html", user, food=food, units=units, meals=meals, meal=meal,
                  day=parse_day(d), default_unit=default_unit, per100=services.per_100g(food), nav="add")


@app.post("/log")
async def log_submit(request: Request, user: User = CurrentUser, session: Session = DB):
    form = await request.form()
    day = parse_day(form.get("d"))
    food = session.get(Food, as_int(form.get("food_id")) or 0)
    meal = services.get_meal(session, user, as_int(form.get("meal_id")))
    amount = nutrition.to_float(form.get("amount"))
    if food is None or not services.can_see(food, user) or meal is None or amount is None:
        raise HTTPException(400, "Missing food, meal or amount")
    unit = form.get("unit", "g")
    grams = amount
    if unit != "g":
        match = next((u for u in services.units_for(session, food) if str(u.id) == unit), None)
        if match is None:
            raise HTTPException(400, "Unknown unit")
        grams = amount * match.grams
    try:
        services.log_food(session, user, food, grams, meal, day)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return go(f"/today?d={day.isoformat()}")


@app.post("/log/{entry_id}/delete")
def log_delete(entry_id: int, user: User = CurrentUser, session: Session = DB):
    day = services.delete_entry(session, user, entry_id) or services.today()
    return go(f"/today?d={day.isoformat()}")


@app.get("/history")
def history_page(request: Request, user: User = CurrentUser, session: Session = DB):
    end = services.today()
    days = services.history(session, user, end)
    past = [x["kcal"] for x in days[:-1] if x["kcal"] > 0]
    average = round(sum(past) / len(past)) if past else None
    top = max([x["kcal"] for x in days] + [x["goal"] for x in days] + [1]) * 1.1
    for x in days:
        x["height"] = round(x["kcal"] / top * 100, 1)
        x["over"] = x["kcal"] > x["goal"]
        x["is_today"] = x["day"] == end
    goal_line = round(days[-1]["goal"] / top * 100, 1)
    return render(request, "history.html", user, days=days, average=average, goal=days[-1]["goal"],
                  goal_line=goal_line, logged_days=len(past), nav="history")


@app.get("/settings")
def settings_page(request: Request, saved: int = 0, user: User = CurrentUser, session: Session = DB):
    goal = services.goal_on(session, user, services.today())
    return render(request, "settings.html", user, goal=goal, saved=bool(saved), nav="settings")


@app.post("/settings")
async def settings_submit(request: Request, user: User = CurrentUser, session: Session = DB):
    form = await request.form()

    def whole(name):
        value = nutrition.to_float(form.get(name))
        return int(value) if value else None

    kcal = whole("kcal")
    if kcal and 500 <= kcal <= 10000:
        goal = services.goal_on(session, user, services.today())
        new = (kcal, whole("protein_g"), whole("carbs_g"), whole("fat_g"))
        if new != (goal.kcal, goal.protein_g, goal.carbs_g, goal.fat_g):
            services.set_goal(session, user, *new)
    theme = form.get("theme")
    if theme in ("system", "light", "dark"):
        user.theme = theme
        session.add(user)
        session.commit()
    return go("/settings?saved=1")


# ---------- JSON API (same services, different output) ----------

@app.get("/api/day")
def api_day(d: str | None = None, user: User = CurrentUser, session: Session = DB):
    s = services.day_summary(session, user, parse_day(d))
    return {
        "day": s["day"].isoformat(), "goal": s["goal"], "eaten": s["eaten"], "remaining": s["remaining"],
        "macros": s["macros"],
        "meals": [{"name": b["meal"].name, "kcal": b["kcal"],
                   "entries": [e.model_dump(mode="json") for e in b["entries"]]} for b in s["meals"]],
    }


@app.get("/api/foods/search")
def api_search(q: str, user: User = CurrentUser, session: Session = DB):
    return [f.model_dump(mode="json", exclude={"raw_data"}) for f in services.search_foods(session, user, q)]
