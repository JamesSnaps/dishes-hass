from __future__ import annotations

from datetime import datetime

import pytest
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import API, LONDON, mock_api, setup

TODO = "todo.dishes_shopping_list"


def calls(aioclient_mock: AiohttpClientMocker, method: str) -> list[tuple]:
    return [(str(c[1]), c[2]) for c in aioclient_mock.mock_calls if c[0].lower() == method]


async def test_shopping_list(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock)
    aioclient_mock.post(f"{API}/shopping-list/quick-add", json={"added": "2 pints of milk"})
    aioclient_mock.patch(f"{API}/shopping-list/items/i1", json={"id": "i1"})
    aioclient_mock.delete(f"{API}/shopping-list/items/i2", json={"deleted": "i2"})
    aioclient_mock.delete(f"{API}/shopping-list/items/gone", status=404)
    await setup(hass, config_entry)

    assert hass.states.get(TODO).state == "1"  # unchecked items
    items = await hass.services.async_call(
        TODO_DOMAIN, "get_items", target={"entity_id": TODO}, blocking=True, return_response=True
    )
    milk = items[TODO]["items"][0]
    assert (milk["summary"], milk["status"], milk["description"]) == ("Milk", "needs_action", "2 litres")

    await hass.services.async_call(
        TODO_DOMAIN, "add_item", {"item": "2 pints of milk"}, target={"entity_id": TODO}, blocking=True
    )
    assert calls(aioclient_mock, "post") == [
        (f"{API}/shopping-list/quick-add", {"text": "2 pints of milk"})
    ]

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": "i1", "status": "completed", "rename": "Oat milk"},
        target={"entity_id": TODO},
        blocking=True,
    )
    assert calls(aioclient_mock, "patch") == [
        (f"{API}/shopping-list/items/i1", {"ingredientName": "Oat milk", "isChecked": True})
    ]

    # Removing an item someone already removed in Dishes is fine.
    await hass.services.async_call(
        TODO_DOMAIN, "remove_item", {"item": ["i2"]}, target={"entity_id": TODO}, blocking=True
    )
    assert [c[0] for c in calls(aioclient_mock, "delete")] == [f"{API}/shopping-list/items/i2"]


async def test_shopping_list_read_only(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock, scopes=["read:meal_plan", "read:shopping_list"])
    await setup(hass, config_entry)

    assert hass.states.get(TODO).attributes.get("supported_features", 0) == 0
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TODO_DOMAIN, "add_item", {"item": "Eggs"}, target={"entity_id": TODO}, blocking=True
        )


async def test_calendar(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    later = {"weekStartDate": "2026-11-02", "timezone": "Europe/London", "entries": []}
    mock_api(aioclient_mock, weeks={"2026-11-02": later})
    await setup(hass, config_entry)

    state = hass.states.get("calendar.dishes_meal_plan")
    assert state.state == "off"
    assert state.attributes["message"] == "Dinner: Sunday roast & Trifle"
    assert state.attributes["start_time"] == "2026-10-20 17:30:00"

    # Three weeks: two from the coordinator, one fetched for the calendar.
    result = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "start_date_time": datetime(2026, 10, 19, tzinfo=LONDON),
            "end_date_time": datetime(2026, 11, 8, tzinfo=LONDON),
        },
        target={"entity_id": "calendar.dishes_meal_plan"},
        blocking=True,
        return_response=True,
    )
    events = result["calendar.dishes_meal_plan"]["events"]
    assert [e["summary"] for e in events] == [
        "Dinner: Stir-fry",
        "Breakfast: Porridge",
        "Dinner: Sunday roast & Trifle",
        "Dinner: Curry",
        "Dinner: Fish Pie",
    ]
    roast = events[2]
    assert roast["start"] == "2026-10-20T17:30:00+01:00"
    assert roast["description"].splitlines() == [
        "Roast Chicken",
        "Roast Potatoes",
        "Trifle",
        "https://dishes.test/recipes/r-chicken",
    ]
    assert any("week=2026-11-02" in c[0] for c in calls(aioclient_mock, "get"))


async def test_diagnostics_redact_token(
    hass: HomeAssistant,
    frozen,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    mock_api(aioclient_mock)
    await setup(hass, config_entry)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag["entry"]["data"]["token"] == "**REDACTED**"
    assert diag["scopes"] == sorted(diag["scopes"])
    assert diag["cooking"]["cooking"] is True
