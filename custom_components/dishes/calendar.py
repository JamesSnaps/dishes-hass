from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import DishesConfigEntry
from .api import DishesError
from .coordinator import MealPlanCoordinator
from .entity import DishesEntity
from .models import Meal, build_meals

# The calendar's month view asks for about six weeks; past that, fetching each
# week from Dishes isn't worth it.
MAX_WEEKS = 8


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DishesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([MealPlanCalendar(entry.runtime_data.meal_plan, entry)])


class MealPlanCalendar(DishesEntity, CalendarEntity):
    """The meal plan as a calendar: one event per meal, at the time it's served.

    Calendar triggers then work as meal reminders, e.g. an offset of -1:00:00
    for an hour before dinner.
    """

    coordinator: MealPlanCoordinator
    _attr_translation_key = "meal_plan"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator: MealPlanCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "meal_plan")

    def _event(self, meal: Meal) -> CalendarEvent:
        api = self.coordinator.api
        lines = [e["recipe"]["title"] for e in meal.entries]
        if len(lines) == 1 and lines[0] == meal.title:
            lines = []
        lines.append(api.recipe_url(meal.main["recipe"]["id"]))
        return CalendarEvent(
            start=meal.serve_at,
            end=meal.ends_at,
            summary=f"{meal.label}: {meal.title}",
            description="\n".join(lines),
            uid=meal.uid,
        )

    @property
    def event(self) -> CalendarEvent | None:
        data = self.coordinator.data
        meal = data.next_meal(dt_util.now()) if data else None
        return self._event(meal) if meal else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        data = self.coordinator.data
        tz = data.tz
        # Weeks already fetched (this one and next) come from the coordinator.
        have = {data.week_start, data.week_start + timedelta(days=7)}
        meals = list(data.meals)

        first = start_date.astimezone(tz).date()
        monday = first - timedelta(days=first.weekday())
        last = end_date.astimezone(tz).date()
        weeks = 0
        while monday <= last and weeks < MAX_WEEKS:
            if monday not in have:
                try:
                    meals += build_meals(await self.coordinator.api.week(monday), tz)
                except DishesError as err:
                    raise HomeAssistantError(f"Couldn't load meals for {monday}: {err}") from err
            monday += timedelta(days=7)
            weeks += 1

        return [
            self._event(m)
            for m in sorted(meals, key=lambda m: m.serve_at)
            if m.ends_at > start_date and m.serve_at < end_date
        ]
