from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import DishesConfigEntry
from .const import CONF_TOKEN

TO_REDACT = {CONF_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DishesConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data
    plan = data.meal_plan.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "scopes": sorted(data.scopes),
        "meal_plan": {
            "timezone": str(plan.tz),
            "today": plan.today.isoformat(),
            "week_start": plan.week_start.isoformat(),
            "plan_status": plan.plan_status,
            "today_response": plan.today_response,
            "meals": [
                {**asdict(m), "date": m.date.isoformat(), "serve_at": m.serve_at.isoformat()}
                for m in plan.meals
            ],
        }
        if plan
        else None,
        "cooking": data.cooking.data if data.cooking else None,
        "shopping_items": len(data.shopping.data.get("items", []))
        if data.shopping and data.shopping.data
        else None,
    }
