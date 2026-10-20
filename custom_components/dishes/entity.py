from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DishesConfigEntry
from .const import CONF_URL, DOMAIN
from .coordinator import DishesCoordinator
from .models import Meal, day_name


class DishesEntity(CoordinatorEntity[DishesCoordinator[Any]]):
    """Every Dishes entity, grouped under one device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DishesCoordinator[Any], entry: DishesConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        # Unique ids predate has_entity_name; keep them so existing entity ids stay put.
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Dishes",
            manufacturer="Dishes",
            model="Meal Planner",
            configuration_url=entry.data[CONF_URL],
        )


class TimedEntity(DishesEntity):
    """An entity whose state moves on with the clock, not only when Dishes is polled.

    The next meal changes once a meal is over, the next timer once it goes off;
    waiting for the next poll would leave either up to half an hour stale.
    """

    _unsub_timed: CALLBACK_TYPE | None = None

    def _next_change(self) -> datetime | None:
        raise NotImplementedError

    @callback
    def _schedule_timed(self) -> None:
        if self._unsub_timed:
            self._unsub_timed()
            self._unsub_timed = None
        if (at := self._next_change()) is not None:
            self._unsub_timed = async_track_point_in_time(self.hass, self._timed_change, at)

    @callback
    def _timed_change(self, _now: datetime) -> None:
        self._unsub_timed = None
        self._schedule_timed()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._schedule_timed()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._schedule_timed()
        super()._handle_coordinator_update()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_timed:
            self._unsub_timed()
            self._unsub_timed = None
        await super().async_will_remove_from_hass()


def meal_attributes(entity: DishesEntity, meal: Meal, *, with_day: bool = True) -> dict[str, Any]:
    """A meal's attributes, the same on every meal sensor."""
    api = entity.coordinator.api
    main = meal.main
    recipe = main["recipe"]
    attrs: dict[str, Any] = {
        "meal_type": meal.meal_type,
        "serve_at": meal.serve_at.isoformat() if meal.serve_at_known else None,
        "cuisine": recipe.get("cuisine"),
        "prep_time_minutes": recipe.get("prepTimeMinutes"),
        "cook_time_minutes": recipe.get("cookTimeMinutes"),
        "calories": recipe.get("calories"),
        "servings": main.get("servings"),
        "notes": main.get("notes"),
        "recipe_id": recipe["id"],
        "recipe_url": api.recipe_url(recipe["id"]),
        "cook_url": api.cook_url(recipe["id"]),
        "dishes": [
            {
                "title": e["recipe"]["title"],
                "role": (e.get("mealGroup") or {}).get("role"),
                "recipe_id": e["recipe"]["id"],
                "recipe_url": api.recipe_url(e["recipe"]["id"]),
            }
            for e in meal.entries
        ],
    }
    if with_day:
        attrs = {"day_of_week": day_name(meal), "date": meal.date.isoformat(), **attrs}
    return attrs
