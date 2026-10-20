from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any, TypeVar

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DishesApi, DishesAuthError, DishesError
from .const import (
    CONF_COOKING_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_COOKING_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SHOPPING_SCAN_INTERVAL,
)
from .models import MealPlanData, build_meals

if TYPE_CHECKING:
    from . import DishesConfigEntry

_LOGGER = logging.getLogger(__name__)

_DataT = TypeVar("_DataT")


class DishesCoordinator(DataUpdateCoordinator[_DataT]):
    """Polls one part of the API. A rejected token starts Home Assistant's re-auth."""

    config_entry: DishesConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: DishesConfigEntry,
        api: DishesApi,
        name: str,
        interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {name}",
            update_interval=interval,
        )
        self.api = api

    async def _async_update_data(self) -> _DataT:
        try:
            return await self._fetch()
        except DishesAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except DishesError as err:
            raise UpdateFailed(str(err)) from err

    async def _fetch(self) -> _DataT:
        raise NotImplementedError


class MealPlanCoordinator(DishesCoordinator[MealPlanData]):
    """Today, this week and next week (so "next meal" carries on past Sunday).

    Also polled just after the household's midnight, so "today" turns over on
    time rather than up to a poll interval late.
    """

    _unsub_midnight: CALLBACK_TYPE | None = None

    def __init__(self, hass: HomeAssistant, entry: DishesConfigEntry, api: DishesApi) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, entry, api, "meal plan", timedelta(minutes=minutes))

    @callback
    def _schedule_midnight(self, today: date, tz: Any) -> None:
        self._cancel_midnight()
        at = datetime.combine(today + timedelta(days=1), time(0, 1), tzinfo=tz)
        self._unsub_midnight = async_track_point_in_time(self.hass, self._midnight, at)

    @callback
    def _midnight(self, _now: datetime) -> None:
        self._unsub_midnight = None
        self.hass.async_create_task(self.async_request_refresh())

    @callback
    def _cancel_midnight(self) -> None:
        if self._unsub_midnight:
            self._unsub_midnight()
            self._unsub_midnight = None

    async def async_shutdown(self) -> None:
        self._cancel_midnight()
        await super().async_shutdown()

    async def _fetch(self) -> MealPlanData:
        today = await self.api.today()
        # Dishes before 1.54 has no timezone: fall back to Home Assistant's.
        tz = (
            await dt_util.async_get_time_zone(today["timezone"]) if today.get("timezone") else None
        ) or dt_util.get_default_time_zone()
        today_date = (
            date.fromisoformat(today["date"]) if today.get("date") else dt_util.now(tz).date()
        )

        week = await self.api.week()
        week_start = date.fromisoformat(week["weekStartDate"])
        next_week = await self.api.week(week_start + timedelta(days=7))

        self._schedule_midnight(today_date, tz)
        return MealPlanData(
            tz=tz,
            today=today_date,
            week_start=week_start,
            plan_status=week.get("planStatus", "none"),
            today_response=today,
            week_response=week,
            meals=build_meals(week, tz) + build_meals(next_week, tz),
        )


class CookingCoordinator(DishesCoordinator[dict[str, Any]]):
    """Who's cooking: polled often, since a cook changes step every few minutes."""

    def __init__(self, hass: HomeAssistant, entry: DishesConfigEntry, api: DishesApi) -> None:
        seconds = entry.options.get(CONF_COOKING_INTERVAL, DEFAULT_COOKING_INTERVAL)
        super().__init__(hass, entry, api, "cooking", timedelta(seconds=seconds))

    async def _fetch(self) -> dict[str, Any]:
        return await self.api.cooking()

    @property
    def sessions(self) -> list[dict[str, Any]]:
        return (self.data or {}).get("sessions", [])

    @property
    def members(self) -> list[dict[str, Any]]:
        return (self.data or {}).get("members", [])

    def running_timers(self, now: datetime) -> list[dict[str, Any]]:
        """Every timer still counting down, soonest first, with its cook."""
        timers: list[dict[str, Any]] = []
        for session in self.sessions:
            for timer in session.get("timers", []):
                ends_at = dt_util.parse_datetime(timer["endsAt"]) if timer.get("endsAt") else None
                if timer.get("state") == "running" and ends_at and ends_at > now:
                    timers.append({**timer, "ends_at": ends_at, "session": session})
        return sorted(timers, key=lambda t: t["ends_at"])


class ShoppingCoordinator(DishesCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: DishesConfigEntry, api: DishesApi) -> None:
        super().__init__(hass, entry, api, "shopping list", SHOPPING_SCAN_INTERVAL)

    async def _fetch(self) -> dict[str, Any]:
        return await self.api.shopping_list()
