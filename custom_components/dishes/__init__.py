from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DishesApi, DishesAuthError, DishesError
from .const import CONF_TOKEN, CONF_URL, SCOPE_COOKING, SCOPE_SHOPPING_READ
from .coordinator import CookingCoordinator, MealPlanCoordinator, ShoppingCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR, Platform.TODO]


@dataclass
class DishesRuntimeData:
    api: DishesApi
    scopes: frozenset[str]
    meal_plan: MealPlanCoordinator
    # None when the token lacks the scope: those entities aren't created.
    cooking: CookingCoordinator | None
    shopping: ShoppingCoordinator | None


type DishesConfigEntry = ConfigEntry[DishesRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: DishesConfigEntry) -> bool:
    api = DishesApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])

    # The token's scopes decide what to set up. Adding a scope to the token in
    # Dishes takes effect when the integration is reloaded.
    try:
        scopes = frozenset((await api.token_info()).get("scopes", []))
    except DishesAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except DishesError as err:
        raise ConfigEntryNotReady(str(err)) from err

    meal_plan = MealPlanCoordinator(hass, entry, api)
    cooking = CookingCoordinator(hass, entry, api) if SCOPE_COOKING in scopes else None
    shopping = ShoppingCoordinator(hass, entry, api) if SCOPE_SHOPPING_READ in scopes else None
    for coordinator in (meal_plan, cooking, shopping):
        if coordinator:
            await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = DishesRuntimeData(api, scopes, meal_plan, cooking, shopping)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: DishesConfigEntry) -> None:
    """Options changed: poll at the new intervals."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DishesConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
