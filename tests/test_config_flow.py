from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.dishes.const import (
    CONF_COOKING_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DOMAIN,
)

from .conftest import API, URL, mock_api, setup


async def test_user_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: f"{URL}/", CONF_TOKEN: " secret "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dishes (The Snaps)"
    assert result["data"] == {CONF_URL: URL, CONF_TOKEN: "secret"}
    assert result["result"].unique_id == URL


async def test_user_flow_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    for kwargs, error in (
        ({"status": 401}, "invalid_auth"),
        ({"status": 500}, "cannot_connect"),
        ({"json": {"name": "x", "household": "y", "scopes": ["read:cooking"]}}, "missing_scope"),
    ):
        aioclient_mock.clear_requests()
        aioclient_mock.get(f"{API}/token", **kwargs)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: URL, CONF_TOKEN: "t"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error}


async def test_reauth(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock)
    await setup(hass, config_entry)

    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: "new"})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_TOKEN] == "new"


async def test_reconfigure(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock)
    await setup(hass, config_entry)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_TOKEN: "more-scopes"}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_TOKEN] == "more-scopes"


async def test_options(
    hass: HomeAssistant, frozen, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_api(aioclient_mock)
    await setup(hass, config_entry)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 15, CONF_COOKING_INTERVAL: 20}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_SCAN_INTERVAL: 15, CONF_COOKING_INTERVAL: 20}
    data = config_entry.runtime_data
    assert data.meal_plan.update_interval.total_seconds() == 15 * 60
    assert data.cooking.update_interval.total_seconds() == 20
