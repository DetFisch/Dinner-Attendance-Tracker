"""Config flow for Dinner Attendance Tracker."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries

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
        """Create a default tracker entry."""
        await self.async_set_unique_id(DEFAULT_TRACKER_ID)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=DEFAULT_TRACKER_NAME,
            data={
                CONF_ID: DEFAULT_TRACKER_ID,
                CONF_NAME: DEFAULT_TRACKER_NAME,
            },
        )

    async def async_step_import(self, user_input: dict[str, Any]):
        """Handle import from YAML."""
        tracker_id = str(user_input.get(CONF_ID, DEFAULT_TRACKER_ID)).strip()
        tracker_name = str(user_input.get(CONF_NAME, tracker_id)).strip() or tracker_id

        await self.async_set_unique_id(tracker_id)
        self._abort_if_unique_id_configured(updates=user_input)

        return self.async_create_entry(
            title=tracker_name,
            data={
                CONF_ID: tracker_id,
                CONF_NAME: tracker_name,
            },
        )
