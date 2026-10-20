from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import DishesConfigEntry
from .coordinator import CookingCoordinator, MealPlanCoordinator
from .entity import DishesEntity, TimedEntity, meal_attributes
from .models import Meal, MealPlanData, day_name

# A sensor's state can't be longer than this.
MAX_STATE_LENGTH = 255

PLAN_STATUSES = ["active", "draft", "archived", "none"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DishesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    meal_plan = data.meal_plan
    entities: list[SensorEntity] = [
        NextMealSensor(meal_plan, entry),
        TodayMealSensor(meal_plan, entry, "dinner", "tonight_dinner"),
        TodayMealSensor(meal_plan, entry, "lunch", "today_lunch"),
        TodayMealSensor(meal_plan, entry, "breakfast", "today_breakfast"),
        WeekPlanSensor(meal_plan, entry),
        DinnerTimeSensor(meal_plan, entry),
        StartCookingSensor(meal_plan, entry),
        NextDeliverySensor(meal_plan, entry),
        OrderDeadlineSensor(meal_plan, entry),
    ]
    if data.cooking:
        entities += [
            CookSensor(data.cooking, entry),
            CookingStepSensor(data.cooking, entry),
            NextTimerSensor(data.cooking, entry),
        ]
    async_add_entities(entities)


class MealPlanSensor(DishesEntity, SensorEntity):
    coordinator: MealPlanCoordinator

    @property
    def plan(self) -> MealPlanData:
        return self.coordinator.data


# --- Meals ---------------------------------------------------------------------


class NextMealSensor(TimedEntity, MealPlanSensor):
    """The meal being eaten now, or the next one — into next week on a Sunday night."""

    _attr_translation_key = "next_meal"
    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, coordinator: MealPlanCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "next_meal")

    @property
    def meal(self) -> Meal | None:
        return self.plan.next_meal(dt_util.now()) if self.plan else None

    def _next_change(self) -> datetime | None:
        return self.meal.ends_at if self.meal else None

    @property
    def native_value(self) -> str | None:
        return self.meal.title if self.meal else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return meal_attributes(self, self.meal) if self.meal else {}


class TodayMealSensor(MealPlanSensor):
    _attr_icon = "mdi:food"

    def __init__(
        self,
        coordinator: MealPlanCoordinator,
        entry: DishesConfigEntry,
        meal_type: str,
        translation_key: str,
    ) -> None:
        super().__init__(coordinator, entry, f"today_{meal_type}")
        self._meal_type = meal_type
        self._attr_translation_key = translation_key

    @property
    def meal(self) -> Meal | None:
        return self.plan.today_meal(self._meal_type) if self.plan else None

    @property
    def native_value(self) -> str | None:
        return self.meal.title if self.meal else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return meal_attributes(self, self.meal, with_day=False) if self.meal else {}


class WeekPlanSensor(MealPlanSensor):
    """The week's plan status, with the week's meals for the Dishes week card."""

    _attr_translation_key = "week_plan"
    _attr_icon = "mdi:calendar-week"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = PLAN_STATUSES
    # The card reads these; the recorder needn't keep a copy every half hour.
    _unrecorded_attributes = frozenset({"meals"})

    def __init__(self, coordinator: MealPlanCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "week_plan")

    @property
    def native_value(self) -> str | None:
        if not self.plan:
            return None
        status = self.plan.plan_status
        return status if status in PLAN_STATUSES else "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.plan:
            return {}
        api = self.coordinator.api
        meals = self.plan.this_week()
        return {
            "week_start": self.plan.week_start.isoformat(),
            "today": self.plan.today.isoformat(),
            "meal_count": sum(len(m.entries) for m in meals),
            "dishes_url": api.url,
            "meals": [
                {
                    "date": m.date.isoformat(),
                    "day_of_week": m.date.weekday(),
                    "day": day_name(m),
                    "meal_type": m.meal_type,
                    "title": m.title,
                    "serve_at": m.serve_at.isoformat() if m.serve_at_known else None,
                    "notes": m.main.get("notes"),
                    "url": api.recipe_url(m.main["recipe"]["id"]),
                    "dishes": [e["recipe"]["title"] for e in m.entries],
                }
                for m in meals
            ],
        }


# --- Tonight's dinner ------------------------------------------------------------


class DinnerTimeSensor(MealPlanSensor):
    """When dinner is tonight — the household's dinner time for the day."""

    _attr_translation_key = "dinner_time"
    _attr_icon = "mdi:clock-time-six-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: MealPlanCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "dinner_time")

    @property
    def native_value(self) -> datetime | None:
        dinner = self.plan.dinner if self.plan else None
        return dt_util.parse_datetime(dinner["serveAt"]) if dinner else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dinner = self.plan.dinner if self.plan else None
        if not dinner:
            return {}
        return {"time": dinner["time"], "reminder_enabled": dinner["reminderEnabled"]}


class StartCookingSensor(MealPlanSensor):
    """When to start cooking tonight's dinner to eat on time — what Dishes' reminder goes by."""

    _attr_translation_key = "start_cooking"
    _attr_icon = "mdi:pot-steam-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: MealPlanCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "start_cooking")

    @property
    def native_value(self) -> datetime | None:
        dinner = self.plan.dinner if self.plan else None
        start = dinner.get("startCookingAt") if dinner else None
        return dt_util.parse_datetime(start) if start else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meal = self.plan.today_meal("dinner") if self.plan else None
        return {"dinner": meal.title} if meal else {}


# --- Groceries -----------------------------------------------------------------------


class NextDeliverySensor(MealPlanSensor):
    _attr_translation_key = "next_delivery"
    _attr_icon = "mdi:truck-delivery-outline"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: MealPlanCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "next_delivery")

    @property
    def delivery(self) -> dict[str, Any] | None:
        return self.plan.next_delivery if self.plan else None

    @property
    def native_value(self) -> date | None:
        return date.fromisoformat(self.delivery["date"]) if self.delivery else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.delivery
        if not d:
            return {}
        return {
            "status": d.get("status"),
            "slot": d.get("slot"),
            "total": d.get("total"),
            "order_reference": d.get("orderReference"),
            "order_by": d.get("orderByLabel"),
            "unplanned_dinners": d.get("unplannedDinners"),
            "meals_not_on_list": d.get("mealsNotOnList"),
            "items_not_in_basket": d.get("itemsNotInBasket"),
            "added_since_order": d.get("addedSinceOrder"),
        }


class OrderDeadlineSensor(MealPlanSensor):
    """When the next grocery order closes — for an "order by tonight" reminder."""

    _attr_translation_key = "order_deadline"
    _attr_icon = "mdi:cart-clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: MealPlanCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "order_deadline")

    @property
    def native_value(self) -> datetime | None:
        d = self.plan.next_delivery if self.plan else None
        return dt_util.parse_datetime(d["orderBy"]) if d and d.get("orderBy") else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.plan.next_delivery if self.plan else None
        if not d:
            return {}
        return {"delivery_date": d["date"], "ordered": d.get("status") == "ordered"}


# --- Cooking ---------------------------------------------------------------------------


class CookingSensor(DishesEntity, SensorEntity):
    coordinator: CookingCoordinator

    @property
    def latest(self) -> dict[str, Any] | None:
        """The cook most recently changed — the one to show when there are several."""
        sessions = self.coordinator.sessions
        return max(sessions, key=lambda s: s["updatedAt"]) if sessions else None


class CookSensor(CookingSensor):
    """Who's cooking: their names, or "Nobody"."""

    _attr_translation_key = "cook"
    _attr_icon = "mdi:chef-hat"

    def __init__(self, coordinator: CookingCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "cook")

    @property
    def native_value(self) -> str:
        names: list[str] = []
        for session in self.coordinator.sessions:
            if session["memberName"] not in names:
                names.append(session["memberName"])
        return " & ".join(names) if names else "Nobody"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "cooks": [
                {
                    "member": s["memberName"],
                    "meal": s["title"],
                    "dish": s["dish"],
                    "step": s["step"],
                    "total_steps": s["totalSteps"],
                    "device": s["device"],
                    "started_at": s["startedAt"],
                }
                for s in self.coordinator.sessions
            ]
        }


class CookingStepSensor(CookingSensor):
    """The step on screen in cooking mode — for a kitchen dashboard or a speaker."""

    _attr_translation_key = "cooking_step"
    _attr_icon = "mdi:format-list-numbered"

    def __init__(self, coordinator: CookingCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "cooking_step")

    @property
    def native_value(self) -> str | None:
        session = self.latest
        if not session:
            return None
        text = session["instruction"] or f"Step {session['step']}"
        return text if len(text) <= MAX_STATE_LENGTH else text[: MAX_STATE_LENGTH - 1] + "…"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        session = self.latest
        if not session:
            return {}
        total = session["totalSteps"]
        return {
            "member": session["memberName"],
            "meal": session["title"],
            "dish": session["dish"],
            "step": session["step"],
            "total_steps": total,
            "progress": round(100 * session["step"] / total) if total else None,
            "instruction": session["instruction"],
        }


class NextTimerSensor(TimedEntity, CookingSensor):
    """When the next cooking-mode timer goes off.

    A time trigger on this entity fires right when it ends, between polls too.
    """

    _attr_translation_key = "next_timer"
    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: CookingCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "next_timer")

    @property
    def native_value(self) -> datetime | None:
        timers = self.coordinator.running_timers(dt_util.utcnow())
        return timers[0]["ends_at"] if timers else None

    def _next_change(self) -> datetime | None:
        return self.native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        timers = self.coordinator.running_timers(dt_util.utcnow())
        if not timers:
            return {"running_timers": 0}
        first = timers[0]
        return {
            "label": first["label"],
            "dish": first.get("dish"),
            "member": first["session"]["memberName"],
            "duration_seconds": first.get("durationSeconds"),
            "running_timers": len(timers),
            "timers": [
                {
                    "label": t["label"],
                    "dish": t.get("dish"),
                    "member": t["session"]["memberName"],
                    "ends_at": t["ends_at"].isoformat(),
                }
                for t in timers
            ],
        }
