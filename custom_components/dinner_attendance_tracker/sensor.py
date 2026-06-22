"""Sensor platform for Dinner Attendance Tracker."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DAYS,
    ATTR_DINNER_COUNT_TODAY,
    ATTR_DINNER_TODAY,
    ATTR_OVERNIGHT_COUNT_TODAY,
    ATTR_OVERNIGHT_TODAY,
    ATTR_PARTICIPANTS,
    ATTR_TODAY,
    ATTR_TODAY_KEY,
    ATTR_TRACKER_ID,
    ATTR_TRACKER_TYPE,
    CONF_NAME,
    DATA_ENTRIES,
    DATA_MANAGER,
    DOMAIN,
    TRACKER_TYPE_DINNER_ATTENDANCE,
)
from .manager import DinnerAttendanceManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dinner Attendance Tracker sensor entities."""
    manager: DinnerAttendanceManager = hass.data[DOMAIN][DATA_ENTRIES][entry.entry_id][DATA_MANAGER]
    async_add_entities([DinnerAttendanceSensor(manager)])


class DinnerAttendanceSensor(
    CoordinatorEntity[DinnerAttendanceManager],
    SensorEntity,
):
    """Dinner attendance overview sensor."""

    _attr_icon = "mdi:silverware-fork-knife"
    _attr_has_entity_name = False

    def __init__(self, manager: DinnerAttendanceManager) -> None:
        super().__init__(manager)
        self._attr_unique_id = f"{DOMAIN}_{manager.tracker_id()}"
        self._attr_object_id = manager.tracker_id()

    async def async_added_to_hass(self) -> None:
        """Keep the entity id aligned with the configured tracker id."""
        await super().async_added_to_hass()
        if self.hass is None:
            return

        desired_entity_id = f"sensor.{self.coordinator.tracker_id()}"
        registry = er.async_get(self.hass)
        current_entity_id = registry.async_get_entity_id("sensor", DOMAIN, self.unique_id)
        if current_entity_id is None or current_entity_id == desired_entity_id:
            return
        if registry.async_get(desired_entity_id) is not None:
            return

        registry.async_update_entity(current_entity_id, new_entity_id=desired_entity_id)

    @property
    def name(self) -> str:
        """Return entity name."""
        return str(self.coordinator.tracker_state()[CONF_NAME])

    @property
    def native_value(self) -> int:
        """Return today's dinner count."""
        return int(self.coordinator.tracker_state()[ATTR_DINNER_COUNT_TODAY])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        state = self.coordinator.tracker_state()
        return {
            ATTR_TRACKER_ID: self.coordinator.tracker_id(),
            ATTR_TRACKER_TYPE: TRACKER_TYPE_DINNER_ATTENDANCE,
            ATTR_PARTICIPANTS: state[ATTR_PARTICIPANTS],
            ATTR_DAYS: state[ATTR_DAYS],
            ATTR_TODAY_KEY: state[ATTR_TODAY_KEY],
            ATTR_TODAY: state[ATTR_TODAY],
            ATTR_DINNER_TODAY: state[ATTR_DINNER_TODAY],
            ATTR_OVERNIGHT_TODAY: state[ATTR_OVERNIGHT_TODAY],
            ATTR_DINNER_COUNT_TODAY: state[ATTR_DINNER_COUNT_TODAY],
            ATTR_OVERNIGHT_COUNT_TODAY: state[ATTR_OVERNIGHT_COUNT_TODAY],
        }

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        state = self.coordinator.tracker_state()
        return {
            "identifiers": {(DOMAIN, self.coordinator.tracker_id())},
            "name": str(state[CONF_NAME]),
            "manufacturer": "Custom",
            "model": "Dinner Attendance Tracker",
        }
