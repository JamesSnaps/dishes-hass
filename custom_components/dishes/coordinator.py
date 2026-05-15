from __future__ import annotations

import logging
from datetime import datetime, timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, MEAL_TIME_HOUR, DAY_NAMES

_LOGGER = logging.getLogger(__name__)


class DishesCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        url: str,
        token: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )
        self._session = session
        self._url = url
        self._token = token

    async def _async_update_data(self) -> dict:
        try:
            async with self._session.get(
                f"{self._url}/api/integrations/meal-plan/week",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise UpdateFailed("Invalid or expired integration token")
                if resp.status == 403:
                    raise UpdateFailed("Token is missing read:meal_plan scope")
                if resp.status != 200:
                    raise UpdateFailed(f"Unexpected response: {resp.status}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

    def get_next_meal(self) -> dict | None:
        """Return the next upcoming meal entry based on current time."""
        if not self.data:
            return None

        now = datetime.now()
        today = now.weekday()  # Python Mon=0 .. Sun=6, matches our dayOfWeek format
        current_hour = now.hour

        def sort_key(entry: dict) -> tuple:
            return (entry["dayOfWeek"], MEAL_TIME_HOUR.get(entry["mealType"], 12))

        for entry in sorted(self.data.get("entries", []), key=sort_key):
            day = entry["dayOfWeek"]
            meal_hour = MEAL_TIME_HOUR.get(entry["mealType"], 12)
            if day > today or (day == today and meal_hour >= current_hour):
                return entry

        return None

    def get_today_meal(self, meal_type: str) -> dict | None:
        """Return today's entry for the given meal type, or None."""
        if not self.data:
            return None

        today = datetime.now().weekday()
        for entry in self.data.get("entries", []):
            if entry["dayOfWeek"] == today and entry["mealType"] == meal_type:
                return entry

        return None

    @staticmethod
    def entry_attributes(entry: dict) -> dict:
        """Build a consistent attributes dict from a meal plan entry."""
        recipe = entry["recipe"]
        return {
            "meal_type": entry["mealType"],
            "day_of_week": DAY_NAMES[entry["dayOfWeek"]],
            "cuisine": recipe.get("cuisine"),
            "prep_time_minutes": recipe.get("prepTimeMinutes"),
            "cook_time_minutes": recipe.get("cookTimeMinutes"),
            "servings": entry.get("servings"),
            "notes": entry.get("notes"),
            "recipe_id": recipe["id"],
        }
