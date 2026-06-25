"""Config flow for Crestron Home."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN
from .crestron_home_sdk import CrestronHomeApiError, CrestronHomeClient, CrestronHomeError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
                autocomplete="off",
            ),
        ),
        vol.Required(CONF_TOKEN): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="new-password",
            ),
        ),
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
    }
)


def _entry_title(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname:
        return f"Crestron Home ({parsed.hostname})"
    return "Crestron Home"


class CrestronHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Crestron Home."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            user_input = {**user_input, CONF_URL: url}
            unique_id = url
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates=user_input)
            try:
                await self.hass.async_add_executor_job(
                    _validate_input_sync,
                    user_input,
                )
            except CrestronHomeApiError as err:
                _LOGGER.debug("Crestron login failed: %s", err)
                if err.status_code in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except CrestronHomeError as err:
                _LOGGER.debug("Crestron login failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Crestron Home")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=_entry_title(url),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )


def _validate_input_sync(data: dict[str, Any]) -> None:
    client = CrestronHomeClient(
        data[CONF_URL].rstrip("/"),
        auth_token=data[CONF_TOKEN],
        verify_ssl=data[CONF_VERIFY_SSL],
    )
    try:
        client.login()
    finally:
        try:
            client.logout()
        finally:
            client.close()
