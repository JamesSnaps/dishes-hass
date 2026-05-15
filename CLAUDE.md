# dishes-hass — Claude/Agent Context

## What This Repo Is

A Home Assistant custom integration for the [Dishes](https://github.com/JamesSnaps/dishes-app) self-hosted meal planning app. It polls the Dishes integrations API and exposes the weekly meal plan as persistent HA sensor entities.

---

## Companion App

The Dishes app lives at `https://github.com/JamesSnaps/dishes-app`. The API this integration consumes is documented in that repo's `API.md`. The relevant endpoint is:

```
GET /api/integrations/meal-plan/week
Authorization: Bearer <token>
```

Tokens are created in the Dishes UI under Settings → Integrations and require the `read:meal_plan` scope.

---

## Structure

```
custom_components/dishes/
  __init__.py        entry setup / teardown
  manifest.json      HA integration metadata
  config_flow.py     UI-based setup (URL + token, validated against the API)
  coordinator.py     DataUpdateCoordinator — polls the API, computes next meal
  sensor.py          SensorEntity definitions
  const.py           shared constants (domain, conf keys, meal time map)
  translations/
    en.json          config flow UI strings
hacs.json            HACS metadata
```

---

## Conventions

- Python 3.12+, type annotations throughout, `from __future__ import annotations`
- All HA patterns follow the [HA developer docs](https://developers.home-assistant.io/docs/creating_component_index)
- Use `async_get_clientsession(hass)` — never create a bare `aiohttp.ClientSession`
- All entities use `CoordinatorEntity` so updates are push-based from the coordinator
- All sensors share a single `DeviceInfo` so they group under one device in HA

## Versioning

Bump `version` in `manifest.json` with every release. HACS uses this to detect updates.
Patch (`1.0.x`) for fixes, minor (`1.x.0`) for new sensors or config options.

---

## Adding New Sensors

1. Add a new class in `sensor.py` extending `CoordinatorEntity` and `SensorEntity`
2. Register it in `async_setup_entry` in `sensor.py`
3. If new data is needed, add a helper method to `DishesCoordinator` in `coordinator.py`
4. Update `README.md` sensor table

## Adding New API Endpoints

If the Dishes app adds new integration endpoints (e.g. shopping list, pantry), add them as new platforms (e.g. `todo.py`, `binary_sensor.py`) and register them in `PLATFORMS` in `__init__.py`.
