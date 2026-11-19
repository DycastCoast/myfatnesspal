"""The app's actual logic. Routes call these; these never touch HTML.

Keeping logic here (not in routes) is what makes the app "API-first": the web
pages and the JSON API both call the same functions.
"""

from collections import OrderedDict
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app import nutrition
from app.config import settings
from app.models import Food, FoodUnit, Goal, LogEntry, Meal, User
from app.sources import openfoodfacts as off

DEFAULT_MEALS = [
    ("Breakfast", "breakfast"),
    ("Lunch", "lunch"),
    ("Dinner", "dinner"),
    ("Snacks", "snacks"),
]
MAX_GRAMS = 5000


def today():
    return datetime.now(settings.tz).date()


# ---------- users, meals, goals ----------

def create_user(session: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@")[0])
    session.add(user)
    session.flush()  # gives the user an id before we add meals
    for order, (name, colour) in enumerate(DEFAULT_MEALS):
        session.add(Meal(user_id=user.id, name=name, sort_order=order, colour=colour))
    session.add(Goal(user_id=user.id, kcal=settings.default_goal_kcal, start_date=date(2000, 1, 1)))
    session.commit()
    session.refresh(user)
    return user


def meals_for(session: Session, user: User):
    return session.exec(
        select(Meal).where(Meal.user_id == user.id).order_by(Meal.sort_order)
    ).all()


def get_meal(session: Session, user: User, meal_id):
    meal = session.get(Meal, meal_id) if meal_id else None
    if meal is None or meal.user_id != user.id:
        return None
    return meal


def goal_on(session: Session, user: User, day: date) -> Goal:
    goal = session.exec(
        select(Goal)
        .where(Goal.user_id == user.id, Goal.start_date <= day)
        .order_by(col(Goal.start_date).desc(), col(Goal.id).desc())
    ).first()
    return goal or Goal(user_id=user.id, kcal=settings.default_goal_kcal, start_date=day)


def set_goal(session: Session, user: User, kcal, protein_g, carbs_g, fat_g):
    session.add(Goal(user_id=user.id, kcal=kcal, protein_g=protein_g, carbs_g=carbs_g,
                     fat_g=fat_g, start_date=today()))
    session.commit()


# ---------- foods ----------

def per_100g(food: Food):
    return {"kcal": food.kcal_100g, "protein": food.protein_100g,
            "carbs": food.carbs_100g, "fat": food.fat_100g}


def can_see(food: Food, user: User):
    return food.visibility == "shared" or food.created_by == user.id


def units_for(session: Session, food: Food):
    return session.exec(select(FoodUnit).where(FoodUnit.food_id == food.id)).all()


def find_by_barcode(session: Session, barcode: str, user: User):
    foods = session.exec(select(Food).where(Food.barcode == barcode)).all()
    visible = [f for f in foods if can_see(f, user)]
    # Prefer a friend's version over the database one if both exist.
    visible.sort(key=lambda f: f.source != "custom")
    return visible[0] if visible else None


def save_food(session: Session, data: dict) -> Food:
    units = data.pop("units", [])
    food = Food(**data)
    session.add(food)
    session.flush()
    for unit in units:
        session.add(FoodUnit(food_id=food.id, name=unit["name"], grams=unit["grams"]))
    session.commit()
    session.refresh(food)
    return food


async def get_or_fetch_barcode(session: Session, barcode: str, user: User):
    """Our database first (instant, works offline), then Open Food Facts."""
    food = find_by_barcode(session, barcode, user)
    if food:
        return food
    payload = await off.fetch_product(barcode, settings.off_timeout, settings.contact)
    mapped = off.map_product(barcode, payload)
    if mapped is None:
        return None
    return save_food(session, mapped)


def search_foods(session: Session, user: User, query: str, limit=30):
    query = query.strip()
    if not query:
        return []
    pattern = f"%{query.lower()}%"
    foods = session.exec(
        select(Food)
        .where(or_(func.lower(Food.name).like(pattern), func.lower(Food.brand).like(pattern)))
        .where(or_(Food.visibility == "shared", Food.created_by == user.id))
        .limit(200)
    ).all()
    q = query.lower()
    foods.sort(key=lambda f: (not f.name.lower().startswith(q), f.source != "custom", len(f.name)))
    return foods[:limit]


def recent_foods(session: Session, user: User, limit=8):
    rows = session.exec(
        select(LogEntry.food_id, func.max(LogEntry.created_at).label("last"))
        .where(LogEntry.user_id == user.id)
        .group_by(LogEntry.food_id)
        .order_by(func.max(LogEntry.created_at).desc())
        .limit(limit)
    ).all()
    foods = [session.get(Food, food_id) for food_id, _ in rows]
    return [f for f in foods if f is not None and can_see(f, user)]


def create_custom_food(session: Session, user: User, form: dict) -> Food:
    name = (form.get("name") or "").strip()
    kcal = nutrition.to_float(form.get("kcal_100g"))
    if not name:
        raise ValueError("Give the food a name.")
    if kcal is None:
        raise ValueError("Calories per 100 g are required.")
    fields = {k: nutrition.to_float(form.get(k)) for k in (
        "protein_100g", "carbs_100g", "fat_100g", "fibre_100g", "sugar_100g", "salt_100g")}
    if nutrition.is_suspicious(kcal, fields["protein_100g"], fields["carbs_100g"], fields["fat_100g"]):
        raise ValueError("Those numbers can't all be right per 100 g. Check the label.")
    barcode = (form.get("barcode") or "").strip() or None
    if barcode and not off.is_valid_barcode(barcode):
        raise ValueError("A barcode is 6 to 14 digits.")
    serving_g = nutrition.to_float(form.get("serving_g"))
    units = [{"name": "serving", "grams": serving_g}] if serving_g else []
    unit_name = (form.get("unit_name") or "").strip().lower()
    unit_grams = nutrition.to_float(form.get("unit_grams"))
    if unit_name and unit_grams:
        units.append({"name": unit_name, "grams": unit_grams})
    return save_food(session, {
        "name": name,
        "brand": (form.get("brand") or "").strip() or None,
        "barcode": barcode,
        "source": "custom",
        "created_by": user.id,
        "kcal_100g": kcal,
        **fields,
        "serving_g": serving_g,
        "units": units,
    })


# ---------- logging ----------

def log_food(session: Session, user: User, food: Food, grams: float, meal: Meal, day: date):
    if not 0 < grams <= MAX_GRAMS:
        raise ValueError(f"Amount must be between 0 and {MAX_GRAMS} g.")
    snap = nutrition.scale(per_100g(food), grams)
    entry = LogEntry(user_id=user.id, food_id=food.id, meal_id=meal.id, day=day,
                     grams=round(grams, 1), food_name=food.name, **snap)
    session.add(entry)
    session.commit()
    return entry


def delete_entry(session: Session, user: User, entry_id: int):
    entry = session.get(LogEntry, entry_id)
    if entry is None or entry.user_id != user.id:  # can only delete your own
        return None
    day = entry.day
    session.delete(entry)
    session.commit()
    return day


def day_summary(session: Session, user: User, day: date):
    entries = session.exec(
        select(LogEntry).where(LogEntry.user_id == user.id, LogEntry.day == day)
        .order_by(LogEntry.created_at)
    ).all()
    by_meal = OrderedDict((m.id, {"meal": m, "entries": [], "kcal": 0}) for m in meals_for(session, user))
    for e in entries:
        if e.meal_id in by_meal:
            by_meal[e.meal_id]["entries"].append(e)
    for block in by_meal.values():
        block["kcal"] = round(sum(e.kcal or 0 for e in block["entries"]))

    goal = goal_on(session, user, day)
    eaten = round(sum(e.kcal or 0 for e in entries))
    macros = []
    for key, label, goal_value in (("protein", "Protein", goal.protein_g),
                                   ("carbs", "Carbs", goal.carbs_g),
                                   ("fat", "Fat", goal.fat_g)):
        total, complete = nutrition.sum_known(getattr(e, key) for e in entries)
        pct = min(100, round(total / goal_value * 100)) if goal_value else None
        macros.append({"key": key, "label": label, "total": round(total), "goal": goal_value,
                       "pct": pct, "complete": complete})
    return {
        "day": day,
        "meals": list(by_meal.values()),
        "goal": goal.kcal,
        "eaten": eaten,
        "remaining": goal.kcal - eaten,
        "fraction": min(1.0, eaten / goal.kcal) if goal.kcal else 0,
        "macros": macros,
        "unknown_kcal": any(e.kcal is None for e in entries),
    }


def history(session: Session, user: User, end: date, days=7):
    start = end - timedelta(days=days - 1)
    rows = session.exec(
        select(LogEntry.day, func.sum(LogEntry.kcal))
        .where(LogEntry.user_id == user.id, LogEntry.day >= start, LogEntry.day <= end)
        .group_by(LogEntry.day)
    ).all()
    totals = {d: round(k or 0) for d, k in rows}
    result = []
    for i in range(days):
        d = start + timedelta(days=i)
        result.append({"day": d, "kcal": totals.get(d, 0), "goal": goal_on(session, user, d).kcal})
    return result
