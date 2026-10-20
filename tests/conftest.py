from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.dishes.const import CONF_TOKEN, CONF_URL, DOMAIN

URL = "https://dishes.test"
API = f"{URL}/api/integrations"
LONDON = ZoneInfo("Europe/London")

# Tuesday 20 October 2026, 14:00 in London (BST, UTC+1).
NOW = datetime(2026, 10, 20, 14, 0, tzinfo=LONDON)
MEMBER_JAMES = "45c48cce-2e2d-4fbd-8a5c-1b2c3d4e5f60"
MEMBER_SAM = "d3d94468-02a4-4b1e-9c3d-2e3f4a5b6c71"
ALL_SCOPES = ["read:meal_plan", "read:cooking", "read:shopping_list", "write:shopping_list"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


@pytest.fixture
async def frozen(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(NOW)
    return freezer


def recipe(rid: str, title: str) -> dict[str, Any]:
    return {
        "id": rid,
        "title": title,
        "cuisine": "British",
        "prepTimeMinutes": 20,
        "cookTimeMinutes": 40,
        "calories": 600,
    }


def entry(day: int, meal: str, rid: str, title: str, serve: str | None, group: dict | None = None):
    return {
        "id": f"e-{day}-{meal}-{rid}",
        "dayOfWeek": day,
        "mealType": meal,
        "servings": "4",
        "notes": None,
        "serveAt": serve,
        "mealGroup": group,
        "recipe": recipe(rid, title),
    }


ROAST = {"id": "g1", "title": "Sunday roast", "role": "main"}
ROAST_SIDE = {"id": "g1", "title": "Sunday roast", "role": "side"}


def week_payload() -> dict[str, Any]:
    return {
        "weekStartDate": "2026-10-19",
        "timezone": "Europe/London",
        "planStatus": "active",
        "entries": [
            entry(0, "dinner", "r-stirfry", "Stir-fry", "2026-10-19T16:00:00.000Z"),
            entry(1, "breakfast", "r-oats", "Porridge", None),
            # Tonight: a combined meal (main + side) and a pudding on its own.
            entry(1, "dinner", "r-chicken", "Roast Chicken", "2026-10-20T16:30:00.000Z", ROAST),
            entry(1, "dinner", "r-potatoes", "Roast Potatoes", "2026-10-20T16:30:00.000Z", ROAST_SIDE),
            entry(1, "dinner", "r-trifle", "Trifle", "2026-10-20T16:30:00.000Z"),
            entry(6, "dinner", "r-curry", "Curry", "2026-10-25T17:00:00.000Z"),
        ],
    }


def next_week_payload() -> dict[str, Any]:
    return {
        "weekStartDate": "2026-10-26",
        "timezone": "Europe/London",
        "planStatus": "draft",
        "entries": [entry(0, "dinner", "r-pie", "Fish Pie", "2026-10-26T17:00:00.000Z")],
    }


def today_payload() -> dict[str, Any]:
    return {
        "date": "2026-10-20",
        "timezone": "Europe/London",
        "meals": [],
        "dinner": {
            "time": "17:30",
            "serveAt": "2026-10-20T16:30:00.000Z",
            "startCookingAt": "2026-10-20T15:20:00.000Z",
            "reminderEnabled": True,
        },
        "nextDelivery": {
            "date": "2026-10-22",
            "status": "scheduled",
            "slot": None,
            "total": None,
            "orderReference": None,
            "orderBy": "2026-10-21T22:00:00.000Z",
            "orderByLabel": "23:00 tomorrow",
            "covers": [],
            "unplannedDinners": [],
            "mealsNotOnList": [],
            "itemsNotInBasket": 3,
            "addedSinceOrder": [],
        },
    }


def cooking_payload(cooking: bool = True) -> dict[str, Any]:
    sessions = (
        [
            {
                "id": "s1",
                "memberId": MEMBER_JAMES,
                "memberName": "James",
                "title": "Sunday roast",
                "dish": "Roast Chicken",
                "step": 3,
                "totalSteps": 8,
                "instruction": "Baste the chicken.",
                "device": "iPad",
                "startedAt": "2026-10-20T12:30:00.000Z",
                "updatedAt": "2026-10-20T12:55:00.000Z",
                "timers": [
                    {
                        "id": "t1",
                        "label": "Roast",
                        "dish": "Roast Chicken",
                        "state": "running",
                        "endsAt": "2026-10-20T13:25:00.000Z",
                        "remainingSeconds": 1500,
                        "durationSeconds": 3000,
                    },
                    {
                        "id": "t2",
                        "label": "Potatoes",
                        "dish": "Roast Potatoes",
                        "state": "running",
                        "endsAt": "2026-10-20T13:40:00.000Z",
                        "remainingSeconds": 2400,
                        "durationSeconds": 2400,
                    },
                    {
                        "id": "t3",
                        "label": "Rest",
                        "dish": None,
                        "state": "paused",
                        "endsAt": None,
                        "remainingSeconds": 600,
                        "durationSeconds": 600,
                    },
                ],
            }
        ]
        if cooking
        else []
    )
    return {
        "cooking": cooking,
        "members": [
            {"id": MEMBER_JAMES, "name": "James", "cooking": cooking},
            {"id": MEMBER_SAM, "name": "Sam", "cooking": False},
        ],
        "sessions": sessions,
    }


def shopping_payload() -> dict[str, Any]:
    return {
        "list": {"id": "l1", "name": "Shopping", "createdAt": "2026-10-19T09:00:00.000Z"},
        "items": [
            {"id": "i1", "ingredientName": "Milk", "amount": "2", "unit": "litres", "category": "dairy", "isChecked": False, "position": 0},
            {"id": "i2", "ingredientName": "Bread", "amount": None, "unit": None, "category": None, "isChecked": True, "position": 1},
        ],
    }


def mock_api(
    aioclient_mock: AiohttpClientMocker,
    scopes: list[str] | None = None,
    *,
    cooking: bool = True,
    cooking_data: dict[str, Any] | None = None,
    weeks: dict[str, dict[str, Any]] | None = None,
) -> None:
    aioclient_mock.get(
        f"{API}/token",
        json={"name": "HA", "household": "The Snaps", "scopes": ALL_SCOPES if scopes is None else scopes},
    )
    aioclient_mock.get(f"{API}/today", json=today_payload())
    # Most specific first: the mock answers with the first URL that matches.
    for monday, payload in (weeks or {}).items():
        aioclient_mock.get(f"{API}/meal-plan/week?week={monday}", json=payload)
    aioclient_mock.get(f"{API}/meal-plan/week?week=2026-10-26", json=next_week_payload())
    aioclient_mock.get(f"{API}/meal-plan/week", json=week_payload())
    aioclient_mock.get(f"{API}/cooking", json=cooking_data or cooking_payload(cooking))
    aioclient_mock.get(f"{API}/shopping-list", json=shopping_payload())


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Dishes (The Snaps)",
        unique_id=URL,
        data={CONF_URL: URL, CONF_TOKEN: "secret-token"},
    )


async def setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> MockConfigEntry:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def advance(hass: HomeAssistant, frozen: FrozenDateTimeFactory):
    """Move the clock on and let time-based listeners fire."""
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    async def _advance(delta: timedelta) -> None:
        frozen.tick(delta)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    return _advance
