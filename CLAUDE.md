# dishes-hass — Claude/Agent Context

## What This Repo Is

A Home Assistant custom integration for the [Dishes](https://github.com/JamesSnaps/dishes-app) self-hosted meal planning app. It polls the Dishes integrations API and exposes the meal plan (sensors + calendar), tonight's dinner times, who's cooking with their step and timers, the shopping list (to-do) and grocery deliveries.

---

## Companion App

The Dishes app lives at `https://github.com/JamesSnaps/dishes-app`. The API this integration consumes is documented in that repo's `API.md`. The endpoints it uses:

```
GET    /api/integrations/token                      any token — its scopes decide what's set up
GET    /api/integrations/today                      read:meal_plan
GET    /api/integrations/meal-plan/week[?week=]     read:meal_plan
GET    /api/integrations/cooking                    read:cooking
GET    /api/integrations/shopping-list              read:shopping_list
POST   /api/integrations/shopping-list/quick-add    write:shopping_list
PATCH  /api/integrations/shopping-list/items/{id}   write:shopping_list
DELETE /api/integrations/shopping-list/items/{id}   write:shopping_list
Authorization: Bearer <token>
```

Tokens are created in the Dishes UI under Settings → Integrations. `read:meal_plan` is required; the other scopes each switch on more entities. Dishes before 1.54 has no `/token` (treated as `read:meal_plan` only) and no `timezone`/`serveAt` — keep that fallback working.

---

## Structure

```
custom_components/dishes/
  __init__.py        entry setup / teardown, DishesRuntimeData (entry.runtime_data)
  manifest.json      HA integration metadata
  api.py             DishesApi client + error types (401 → auth, 403 → scope, 404 → not found)
  config_flow.py     setup, reauth, reconfigure, options (poll intervals)
  coordinator.py     MealPlanCoordinator (today + this week + next), CookingCoordinator, ShoppingCoordinator
  models.py          Meal / MealPlanData — entries grouped into one meal per day + meal type
  entity.py          DishesEntity base (device, unique id), TimedEntity, meal attributes
  sensor.py          meal, dinner-time, delivery and cooking sensors
  binary_sensor.py   cooking + one per household member
  calendar.py        meal plan calendar
  todo.py            shopping list
  diagnostics.py     config entry diagnostics (token redacted)
  const.py           shared constants (domain, conf keys, scopes, default meal times)
  translations/
    en.json          config flow + entity names
www/dishes-week-card.js   Lovelace card — reads the week sensor's `meals` attribute (no token)
tests/               pytest-homeassistant-custom-component tests
hacs.json            HACS metadata (minimum HA version)
```

---

## Conventions

- Python 3.12+, type annotations throughout, `from __future__ import annotations`
- All HA patterns follow the [HA developer docs](https://developers.home-assistant.io/docs/creating_component_index)
- Use `async_get_clientsession(hass)` — never create a bare `aiohttp.ClientSession`
- All entities extend `DishesEntity` (a `CoordinatorEntity`) so updates are push-based from the coordinator, they share one `DeviceInfo`, and names come from `translation_key`
- Never change an entity's unique id (`{entry_id}_{key}`) — existing installs' entity ids hang off it
- State that moves with the clock (next meal, next timer) uses `TimedEntity` rather than waiting for a poll
- Run `pytest` before committing (`pip install -r requirements_test.txt`)

## Versioning

Bump `version` in `manifest.json` with every release. HACS uses this to detect updates.
Patch (`1.0.x`) for fixes, minor (`1.x.0`) for new sensors or config options, major (`x.0.0`) when something users set up stops working as it was (2.0.0: the card dropped its URL/token config).

---

## Adding New Sensors

1. Add a new class in `sensor.py` extending `DishesEntity` and `SensorEntity`, with a `translation_key` named in `translations/en.json`
2. Register it in `async_setup_entry` in `sensor.py`
3. If new data is needed, add it to the right coordinator in `coordinator.py` (or `MealPlanData` in `models.py`)
4. Add a test in `tests/` and update the `README.md` entity tables

## Adding New API Endpoints

If the Dishes app adds new integration endpoints (e.g. pantry), add a method to `DishesApi`, a coordinator if it needs its own poll, and new platforms registered in `PLATFORMS` in `__init__.py`. Gate anything that needs a new scope on `entry.runtime_data.scopes`.
