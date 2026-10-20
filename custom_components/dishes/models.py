"""The meal plan as Home Assistant sees it: one Meal per day and meal type."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, tzinfo
from typing import Any

from homeassistant.util import dt as dt_util

from .const import DAY_NAMES, MEAL_DEFAULT_TIME, MEAL_DURATION, MEAL_LABELS


@dataclass(frozen=True)
class Meal:
    """Everything planned for one meal: a combined meal, or dishes on their own.

    Dishes keeps each recipe as its own entry, so a roast with three sides is
    four entries sharing a meal group. Home Assistant shows them as one meal.
    """

    date: date
    meal_type: str
    title: str
    serve_at: datetime
    # False when Dishes had no time for it and MEAL_DEFAULT_TIME was used.
    serve_at_known: bool
    entries: tuple[dict[str, Any], ...]

    @property
    def uid(self) -> str:
        return f"{self.date.isoformat()}-{self.meal_type}"

    @property
    def ends_at(self) -> datetime:
        return self.serve_at + MEAL_DURATION

    @property
    def label(self) -> str:
        return MEAL_LABELS.get(self.meal_type, self.meal_type.title())

    @property
    def main(self) -> dict[str, Any]:
        """The entry that speaks for the meal: its main dish, else the first."""
        for entry in self.entries:
            if (entry.get("mealGroup") or {}).get("role") == "main":
                return entry
        return self.entries[0]


def meal_title(entries: list[dict[str, Any]]) -> str:
    """A combined meal by its name, dishes on their own by theirs: "Sunday roast & Trifle"."""
    parts: list[str] = []
    for entry in entries:
        group = entry.get("mealGroup")
        part = group["title"] if group else entry["recipe"]["title"]
        if part not in parts:
            parts.append(part)
    return " & ".join(parts)


def build_meals(week: dict[str, Any], tz: tzinfo) -> list[Meal]:
    """One week's entries as meals, in serving order."""
    week_start = date.fromisoformat(week["weekStartDate"])
    slots: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for entry in week.get("entries", []):
        slots.setdefault((entry["dayOfWeek"], entry["mealType"]), []).append(entry)

    meals: list[Meal] = []
    for (day, meal_type), entries in slots.items():
        meal_date = week_start + timedelta(days=day)
        times = sorted(
            parsed
            for e in entries
            if e.get("serveAt") and (parsed := dt_util.parse_datetime(e["serveAt"]))
        )
        if times:
            serve_at, known = times[0].astimezone(tz), True
        else:
            default = MEAL_DEFAULT_TIME.get(meal_type, MEAL_DEFAULT_TIME["lunch"])
            serve_at, known = datetime.combine(meal_date, default, tzinfo=tz), False
        meals.append(
            Meal(
                date=meal_date,
                meal_type=meal_type,
                title=meal_title(entries),
                serve_at=serve_at,
                serve_at_known=known,
                entries=tuple(entries),
            )
        )
    return sorted(meals, key=lambda m: m.serve_at)


@dataclass
class MealPlanData:
    """This week and next, on the household's clock."""

    tz: tzinfo
    today: date
    week_start: date
    plan_status: str
    today_response: dict[str, Any]
    week_response: dict[str, Any]
    meals: list[Meal] = field(default_factory=list)

    def next_meal(self, now: datetime) -> Meal | None:
        """The meal being eaten now, or the next one to come (up to a week ahead)."""
        return next((m for m in self.meals if m.ends_at > now), None)

    def today_meal(self, meal_type: str) -> Meal | None:
        return next(
            (m for m in self.meals if m.date == self.today and m.meal_type == meal_type),
            None,
        )

    def this_week(self) -> list[Meal]:
        end = self.week_start + timedelta(days=7)
        return [m for m in self.meals if self.week_start <= m.date < end]

    @property
    def dinner(self) -> dict[str, Any] | None:
        """Tonight's dinner times (Dishes 1.54+)."""
        return self.today_response.get("dinner")

    @property
    def next_delivery(self) -> dict[str, Any] | None:
        return self.today_response.get("nextDelivery")


def day_name(meal: Meal) -> str:
    return DAY_NAMES[meal.date.weekday()]
