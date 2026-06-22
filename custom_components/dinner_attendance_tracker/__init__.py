"""Dinner Attendance Tracker custom integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ID,
    CONF_NAME,
    CONF_TRACKERS,
    DATA_CARD_REGISTERED,
    DATA_ENTRIES,
    DATA_MANAGER,
    DATA_SERVICES_REGISTERED,
    DAY_KEYS,
    DEFAULT_TRACKER_ID,
    DEFAULT_TRACKER_NAME,
    DOMAIN,
    FIELD_DAY,
    FIELD_DINNER,
    FIELD_ENTITY_ID,
    FIELD_NAME,
    FIELD_OVERNIGHT,
    FIELD_PARTICIPANT_ID,
    FIELD_PERSON_ENTITY_ID,
    SERVICE_ADD_GUEST,
    SERVICE_ADD_PERSON,
    SERVICE_CLEAR_DAY,
    SERVICE_REMOVE_PARTICIPANT,
    SERVICE_RESET_WEEK,
    SERVICE_SET_ATTENDANCE,
)
from .manager import DinnerAttendanceManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]
CARD_FILENAME = "dinner-attendance-card.js"
CARD_URL_PATH = f"/{DOMAIN}/{CARD_FILENAME}"
CARD_FILE_PATH = Path(__file__).parent / CARD_FILENAME

TRACKER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID, default=DEFAULT_TRACKER_ID): cv.slug,
        vol.Required(CONF_NAME, default=DEFAULT_TRACKER_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_TRACKERS): vol.All(
                    cv.ensure_list,
                    [TRACKER_SCHEMA],
                ),
                vol.Optional(CONF_ID, default=DEFAULT_TRACKER_ID): cv.slug,
                vol.Optional(CONF_NAME, default=DEFAULT_TRACKER_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_ADD_PERSON = vol.Schema(
    {
        vol.Optional(FIELD_ENTITY_ID): cv.entity_id,
        vol.Required(FIELD_PERSON_ENTITY_ID): cv.entity_id,
        vol.Optional(FIELD_NAME): cv.string,
    }
)

SERVICE_SCHEMA_ADD_GUEST = vol.Schema(
    {
        vol.Optional(FIELD_ENTITY_ID): cv.entity_id,
        vol.Required(FIELD_NAME): cv.string,
    }
)

SERVICE_SCHEMA_REMOVE_PARTICIPANT = vol.Schema(
    {
        vol.Optional(FIELD_ENTITY_ID): cv.entity_id,
        vol.Required(FIELD_PARTICIPANT_ID): cv.string,
    }
)

SERVICE_SCHEMA_SET_ATTENDANCE = vol.Schema(
    {
        vol.Optional(FIELD_ENTITY_ID): cv.entity_id,
        vol.Required(FIELD_DAY): vol.In(DAY_KEYS),
        vol.Required(FIELD_PARTICIPANT_ID): cv.string,
        vol.Optional(FIELD_DINNER): cv.boolean,
        vol.Optional(FIELD_OVERNIGHT): cv.boolean,
    }
)

SERVICE_SCHEMA_CLEAR_DAY = vol.Schema(
    {
        vol.Optional(FIELD_ENTITY_ID): cv.entity_id,
        vol.Required(FIELD_DAY): vol.In(DAY_KEYS),
    }
)

SERVICE_SCHEMA_RESET_WEEK = vol.Schema({vol.Optional(FIELD_ENTITY_ID): cv.entity_id})


def _ensure_domain_data(hass: HomeAssistant) -> dict[str, Any]:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            DATA_ENTRIES: {},
            DATA_SERVICES_REGISTERED: False,
            DATA_CARD_REGISTERED: False,
        }
    return hass.data[DOMAIN]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Dinner Attendance Tracker from YAML and register card resource."""
    _ensure_domain_data(hass)
    await _ensure_card_registered(hass)

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    trackers = conf.get(CONF_TRACKERS)
    if trackers is None:
        trackers = [
            {
                CONF_ID: conf.get(CONF_ID, DEFAULT_TRACKER_ID),
                CONF_NAME: conf.get(CONF_NAME, DEFAULT_TRACKER_NAME),
            }
        ]

    seen_ids: set[str] = set()
    for tracker in trackers:
        tracker_id = str(tracker[CONF_ID])
        if tracker_id in seen_ids:
            _LOGGER.error("Duplicate tracker id in %s config: %s", DOMAIN, tracker_id)
            return False
        seen_ids.add(tracker_id)

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_ID: tracker_id,
                    CONF_NAME: str(tracker.get(CONF_NAME, tracker_id)),
                },
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dinner Attendance Tracker from a config entry."""
    domain_data = _ensure_domain_data(hass)
    await _ensure_card_registered(hass)

    tracker_id = str(entry.data.get(CONF_ID, DEFAULT_TRACKER_ID))
    tracker_name = str(entry.data.get(CONF_NAME, DEFAULT_TRACKER_NAME))

    manager = DinnerAttendanceManager(
        hass,
        tracker_id=tracker_id,
        tracker_name=tracker_name,
        storage_key=f"{DOMAIN}.{tracker_id}",
    )
    await manager.async_initialize()

    domain_data[DATA_ENTRIES][entry.entry_id] = {DATA_MANAGER: manager}

    if not domain_data[DATA_SERVICES_REGISTERED]:
        _register_services(hass)
        domain_data[DATA_SERVICES_REGISTERED] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Dinner Attendance Tracker config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    domain_data = _ensure_domain_data(hass)
    domain_data[DATA_ENTRIES].pop(entry.entry_id, None)

    if not domain_data[DATA_ENTRIES] and domain_data[DATA_SERVICES_REGISTERED]:
        for service in (
            SERVICE_ADD_PERSON,
            SERVICE_ADD_GUEST,
            SERVICE_REMOVE_PARTICIPANT,
            SERVICE_SET_ATTENDANCE,
            SERVICE_CLEAR_DAY,
            SERVICE_RESET_WEEK,
        ):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
        domain_data[DATA_SERVICES_REGISTERED] = False

    return True


async def _ensure_card_registered(hass: HomeAssistant) -> None:
    """Expose the bundled Lovelace card from inside the integration directory."""
    domain_data = _ensure_domain_data(hass)
    if domain_data[DATA_CARD_REGISTERED]:
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(CARD_FILE_PATH), cache_headers=True)]
    )
    domain_data[DATA_CARD_REGISTERED] = True


def _resolve_manager(hass: HomeAssistant, call_data: dict[str, Any]) -> DinnerAttendanceManager:
    domain_data = _ensure_domain_data(hass)
    entries = domain_data[DATA_ENTRIES]

    entity_id = call_data.get(FIELD_ENTITY_ID)
    if entity_id:
        state = hass.states.get(str(entity_id))
        tracker_id = state.attributes.get("tracker_id") if state is not None else None
        if tracker_id:
            for entry_data in entries.values():
                manager: DinnerAttendanceManager = entry_data[DATA_MANAGER]
                if manager.tracker_id() == tracker_id:
                    return manager
        raise HomeAssistantError("Unknown tracker entity_id")

    if len(entries) == 1:
        return next(iter(entries.values()))[DATA_MANAGER]

    raise HomeAssistantError("Provide entity_id when more than one tracker exists")


def _register_services(hass: HomeAssistant) -> None:
    async def handle_add_person(call: ServiceCall) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_add_person(
            str(call.data[FIELD_PERSON_ENTITY_ID]),
            name=call.data.get(FIELD_NAME),
        )

    async def handle_add_guest(call: ServiceCall) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_add_guest(str(call.data[FIELD_NAME]))

    async def handle_remove_participant(call: ServiceCall) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_remove_participant(str(call.data[FIELD_PARTICIPANT_ID]))

    async def handle_set_attendance(call: ServiceCall) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_set_attendance(
            str(call.data[FIELD_DAY]),
            str(call.data[FIELD_PARTICIPANT_ID]),
            dinner=call.data.get(FIELD_DINNER),
            overnight=call.data.get(FIELD_OVERNIGHT),
        )

    async def handle_clear_day(call: ServiceCall) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_clear_day(str(call.data[FIELD_DAY]))

    async def handle_reset_week(call: ServiceCall) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_reset_week()

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PERSON,
        handle_add_person,
        schema=SERVICE_SCHEMA_ADD_PERSON,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_GUEST,
        handle_add_guest,
        schema=SERVICE_SCHEMA_ADD_GUEST,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_PARTICIPANT,
        handle_remove_participant,
        schema=SERVICE_SCHEMA_REMOVE_PARTICIPANT,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ATTENDANCE,
        handle_set_attendance,
        schema=SERVICE_SCHEMA_SET_ATTENDANCE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_DAY,
        handle_clear_day,
        schema=SERVICE_SCHEMA_CLEAR_DAY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_WEEK,
        handle_reset_week,
        schema=SERVICE_SCHEMA_RESET_WEEK,
    )
