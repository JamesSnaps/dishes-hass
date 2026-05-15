from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_URL, CONF_TOKEN

STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
    }
)


class DishesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            token = user_input[CONF_TOKEN]

            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            error = await self._test_connection(url, token)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="Dishes",
                    data={CONF_URL: url, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SCHEMA,
            errors=errors,
        )

    async def _test_connection(self, url: str, token: str) -> str | None:
        """Return an error key string, or None on success."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{url}/api/integrations/meal-plan/week",
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    return "invalid_auth"
                if resp.status == 403:
                    return "missing_scope"
                if resp.status != 200:
                    return "cannot_connect"
        except aiohttp.ClientError:
            return "cannot_connect"
        return None
