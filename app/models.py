"""Database tables. Matches the data model in the project roadmap."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow():
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    display_name: str
    theme: str = "system"  # system | light | dark
    created_at: datetime = Field(default_factory=utcnow)


class Meal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    sort_order: int = 0
    colour: str = "accent"  # breakfast | lunch | dinner | snacks | accent


class Food(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    barcode: Optional[str] = Field(default=None, index=True)
    name: str = Field(index=True)
    brand: Optional[str] = None
    source: str  # off | cofid | usda | custom
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    visibility: str = "shared"  # shared | private
    # Per 100 g. None = unknown, never 0.
    kcal_100g: Optional[float] = None
    protein_100g: Optional[float] = None
    carbs_100g: Optional[float] = None
    fat_100g: Optional[float] = None
    fibre_100g: Optional[float] = None
    sugar_100g: Optional[float] = None
    salt_100g: Optional[float] = None
    serving_g: Optional[float] = None
    suspicious: bool = False
    raw_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utcnow)


class FoodUnit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    food_id: int = Field(foreign_key="food.id", index=True)
    name: str  # "serving", "biscuit", "slice"
    grams: float


class LogEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    food_id: int = Field(foreign_key="food.id")
    meal_id: int = Field(foreign_key="meal.id")
    day: date = Field(index=True)
    grams: float
    # Snapshot at the time of logging, so editing a food never rewrites history.
    food_name: str
    kcal: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    created_at: datetime = Field(default_factory=utcnow)


class Goal(SQLModel, table=True):
    """A new row per change, so past days keep the goal they had at the time."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kcal: int
    protein_g: Optional[int] = None
    carbs_g: Optional[int] = None
    fat_g: Optional[int] = None
    start_date: date
