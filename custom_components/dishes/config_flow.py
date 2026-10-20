from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import DishesConfigEntry
from .api import DishesApi, DishesAuthError, DishesError
from .const import (
    CONF_COOKING_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_COOKING_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SCOPE_MEAL_PLAN,
)

URL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))
TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class DishesConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, url: str, token: str) -> tuple[str | None, dict[str, Any]]:
        """An error key, or None and the token's details."""
        api = DishesApi(async_get_clientsession(self.hass), url, token)
        try:
            info = await api.token_info()
        except DishesAuthError:
            return "invalid_auth", {}
        except DishesError:
            return "cannot_connect", {}
        if SCOPE_MEAL_PLAN not in info.get("scopes", []):
            return "missing_scope", {}
        return None, info

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            token = user_input[CONF_TOKEN].strip()

            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            error, info = await self._validate(url, token)
            if error:
                errors["base"] = error
            else:
                household = info.get("household")
                return self.async_create_entry(
                    title=f"Dishes ({household})" if household else "Dishes",
                    data={CONF_URL: url, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_URL): URL_SELECTOR, vol.Required(CONF_TOKEN): TOKEN_SELECTOR}),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Dishes turned the token down: it was revoked, or it expired."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            error, _ = await self._validate(entry.data[CONF_URL], token)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): TOKEN_SELECTOR}),
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """A new address for Dishes, or a new token (with more scopes, say)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            token = user_input[CONF_TOKEN].strip()
            await self.async_set_unique_id(url)
            if url != entry.data[CONF_URL]:
                self._abort_if_unique_id_configured()
            error, _ = await self._validate(url, token)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, unique_id=url, data_updates={CONF_URL: url, CONF_TOKEN: token}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_URL): URL_SELECTOR, vol.Required(CONF_TOKEN): TOKEN_SELECTOR}),
                user_input or {CONF_URL: entry.data[CONF_URL]},
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: DishesConfigEntry) -> DishesOptionsFlow:
        return DishesOptionsFlow()


class DishesOptionsFlow(OptionsFlow):
    """How often to poll Dishes."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={k: int(v) for k, v in user_input.items()},
            )

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5, max=240, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_COOKING_INTERVAL,
                    default=options.get(CONF_COOKING_INTERVAL, DEFAULT_COOKING_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10, max=300, step=5, unit_of_measurement="s", mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
