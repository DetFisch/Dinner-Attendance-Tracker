"""Config flow for Dinner Attendance Tracker."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ID,
    CONF_NAME,
    DEFAULT_TRACKER_ID,
    DEFAULT_TRACKER_NAME,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dinner Attendance Tracker."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        if user_input is not None:
            tracker_id = str(user_input[CONF_ID])
            await self.async_set_unique_id(tracker_id)
            self._abort_if_unique_id_configured()

            title = str(user_input.get(CONF_NAME, tracker_id)).strip() or tracker_id
            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ID, default=DEFAULT_TRACKER_ID): cv.slug,
                    vol.Required(CONF_NAME, default=DEFAULT_TRACKER_NAME): str,
                }
            ),
        )

    async def async_step_import(self, user_input: dict[str, Any]):
        """Handle import from YAML."""
        tracker_id = str(user_input[CONF_ID])
        await self.async_set_unique_id(tracker_id)
        self._abort_if_unique_id_configured(updates=user_input)

        title = str(user_input.get(CONF_NAME, DEFAULT_TRACKER_NAME)).strip()
        return self.async_create_entry(title=title or DEFAULT_TRACKER_NAME, data=user_input)
