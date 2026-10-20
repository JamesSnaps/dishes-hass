from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import API, cooking_payload, mock_api, setup


async def test_meal_sensors(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock)
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # A combined meal reads as one meal, with a pudding planned alongside it.
    dinner = hass.states.get("sensor.dishes_tonight_s_dinner")
    assert dinner.state == "Sunday roast & Trifle"
    assert dinner.attributes["recipe_id"] == "r-chicken"  # the main dish speaks for it
    assert [d["title"] for d in dinner.attributes["dishes"]] == [
        "Roast Chicken",
        "Roast Potatoes",
        "Trifle",
    ]
    assert dinner.attributes["recipe_url"] == "https://dishes.test/recipes/r-chicken"
    assert dinner.attributes["cook_url"] == "https://dishes.test/recipes/r-chicken/cook"
    assert dinner.attributes["serve_at"] == "2026-10-20T17:30:00+01:00"

    breakfast = hass.states.get("sensor.dishes_today_s_breakfast")
    assert breakfast.state == "Porridge"
    assert breakfast.attributes["serve_at"] is None  # no time from Dishes

    assert hass.states.get("sensor.dishes_today_s_lunch").state == STATE_UNKNOWN

    next_meal = hass.states.get("sensor.dishes_next_meal")
    assert next_meal.state == "Sunday roast & Trifle"
    assert next_meal.attributes["day_of_week"] == "Tuesday"

    week = hass.states.get("sensor.dishes_week_plan_status")
    assert week.state == "active"
    assert week.attributes["meal_count"] == 6
    assert [m["title"] for m in week.attributes["meals"]] == [
        "Stir-fry",
        "Porridge",
        "Sunday roast & Trifle",
        "Curry",
    ]
    assert week.attributes["dishes_url"] == "https://dishes.test"

    assert hass.states.get("sensor.dishes_dinner_time").state == "2026-10-20T16:30:00+00:00"
    assert hass.states.get("sensor.dishes_start_cooking").state == "2026-10-20T15:20:00+00:00"
    assert hass.states.get("sensor.dishes_next_delivery").state == "2026-10-22"
    assert hass.states.get("sensor.dishes_order_deadline").state == "2026-10-21T22:00:00+00:00"


async def test_next_meal_moves_on_without_a_poll(
    hass: HomeAssistant, advance, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock)
    await setup(hass, config_entry)

    # Dinner is served at 17:30 and stays "next" for an hour.
    await advance(timedelta(hours=4, minutes=29))  # 18:29
    assert hass.states.get("sensor.dishes_next_meal").state == "Sunday roast & Trifle"
    await advance(timedelta(minutes=2))  # 18:31
    assert hass.states.get("sensor.dishes_next_meal").state == "Curry"

    # Past Sunday's dinner it carries on into next week's plan.
    await advance(timedelta(days=5, hours=1))
    assert hass.states.get("sensor.dishes_next_meal").state == "Fish Pie"


async def test_cooking_entities(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock)
    await setup(hass, config_entry)

    assert hass.states.get("binary_sensor.dishes_cooking").state == STATE_ON
    assert hass.states.get("binary_sensor.dishes_james_cooking").state == STATE_ON
    assert hass.states.get("binary_sensor.dishes_sam_cooking").state == STATE_OFF

    cook = hass.states.get("sensor.dishes_cook")
    assert cook.state == "James"
    assert cook.attributes["cooks"][0]["dish"] == "Roast Chicken"

    step = hass.states.get("sensor.dishes_cooking_step")
    assert step.state == "Baste the chicken."
    assert step.attributes["step"] == 3
    assert step.attributes["progress"] == 38

    timer = hass.states.get("sensor.dishes_next_timer")
    assert timer.state == "2026-10-20T13:25:00+00:00"
    assert timer.attributes["label"] == "Roast"
    assert timer.attributes["running_timers"] == 2  # the paused one doesn't count


async def test_next_timer_moves_on_when_one_ends(
    hass: HomeAssistant, advance, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock)
    await setup(hass, config_entry)

    await advance(timedelta(minutes=25, seconds=1))
    timer = hass.states.get("sensor.dishes_next_timer")
    assert timer.state == "2026-10-20T13:40:00+00:00"
    assert timer.attributes["label"] == "Potatoes"

    await advance(timedelta(minutes=15))
    assert hass.states.get("sensor.dishes_next_timer").state == STATE_UNKNOWN


async def test_nobody_cooking(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock, cooking=False)
    await setup(hass, config_entry)

    assert hass.states.get("binary_sensor.dishes_cooking").state == STATE_OFF
    assert hass.states.get("binary_sensor.dishes_james_cooking").state == STATE_OFF
    assert hass.states.get("sensor.dishes_cook").state == "Nobody"
    assert hass.states.get("sensor.dishes_cooking_step").state == STATE_UNKNOWN
    assert hass.states.get("sensor.dishes_next_timer").state == STATE_UNKNOWN


async def test_new_member_gets_a_sensor(
    hass: HomeAssistant, advance, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock)
    await setup(hass, config_entry)
    assert hass.states.get("binary_sensor.dishes_alex_cooking") is None

    payload = cooking_payload()
    payload["members"].append({"id": "m-alex", "name": "Alex", "cooking": False})
    aioclient_mock.clear_requests()
    mock_api(aioclient_mock, cooking_data=payload)

    await advance(timedelta(seconds=31))
    assert hass.states.get("binary_sensor.dishes_alex_cooking").state == STATE_OFF


async def test_scopes_decide_entities(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock, scopes=["read:meal_plan"])
    await setup(hass, config_entry)

    assert hass.states.get("sensor.dishes_next_meal") is not None
    assert hass.states.get("calendar.dishes_meal_plan") is not None
    assert hass.states.get("binary_sensor.dishes_cooking") is None
    assert hass.states.get("sensor.dishes_cook") is None
    assert hass.states.get("todo.dishes_shopping_list") is None
    assert not any("/cooking" in str(call[1]) for call in aioclient_mock.mock_calls)


async def test_old_dishes_without_token_endpoint(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Dishes before 1.54: no token endpoint, no timezone or serve times."""
    week = {
        "weekStartDate": "2026-10-19",
        "planStatus": "active",
        "entries": [
            {
                "id": "e1",
                "dayOfWeek": 1,
                "mealType": "dinner",
                "servings": "4",
                "notes": None,
                "mealGroup": None,
                "recipe": {"id": "r1", "title": "Lasagne", "cuisine": "Italian", "prepTimeMinutes": 20, "cookTimeMinutes": 40},
            }
        ],
    }
    aioclient_mock.get(f"{API}/token", status=404)
    aioclient_mock.get(f"{API}/today", json={"date": "2026-10-20", "meals": [], "nextDelivery": None})
    aioclient_mock.get(f"{API}/meal-plan/week", json=week)
    await setup(hass, config_entry)

    dinner = hass.states.get("sensor.dishes_tonight_s_dinner")
    assert dinner.state == "Lasagne"
    assert dinner.attributes["serve_at"] is None  # 18:00 assumed
    assert hass.states.get("sensor.dishes_dinner_time").state == STATE_UNKNOWN
    assert hass.states.get("binary_sensor.dishes_cooking") is None


async def test_existing_entity_ids_are_kept(
    hass: HomeAssistant,
    frozen,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Entities registered by 1.x keep their ids and history."""
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "sensor", "dishes", f"{config_entry.entry_id}_today_dinner",
        suggested_object_id="tonight_s_dinner", config_entry=config_entry,
    )
    mock_api(aioclient_mock)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.tonight_s_dinner").state == "Sunday roast & Trifle"


async def test_rejected_token_starts_reauth(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    aioclient_mock.get(f"{API}/token", status=401)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_unload(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock)
    await setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
