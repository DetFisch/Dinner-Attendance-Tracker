"""Dinner Attendance Tracker custom integration."""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Any

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
    FIELD_DEFAULT_DINNER,
    FIELD_DEFAULT_OVERNIGHT,
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
    SERVICE_SET_PERSON_DEFAULTS,
    SERVICE_SET_ATTENDANCE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
CARD_FILENAME = "dinner-attendance-card.js"
CARD_URL_PATH = f"/{DOMAIN}/{CARD_FILENAME}"
CARD_FILE_PATH = Path(__file__).parent / CARD_FILENAME


def _ensure_domain_data(hass: Any) -> dict[str, Any]:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            DATA_ENTRIES: {},
            DATA_SERVICES_REGISTERED: False,
            DATA_CARD_REGISTERED: False,
        }
    return hass.data[DOMAIN]


async def async_setup(hass: Any, config: dict[str, Any]) -> bool:
    """Set up Dinner Attendance Tracker from YAML and register card resource."""
    from homeassistant.config_entries import SOURCE_IMPORT

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
    elif not isinstance(trackers, list):
        trackers = [trackers]

    seen_ids: set[str] = set()
    for tracker in trackers:
        if not isinstance(tracker, dict):
            _LOGGER.error("Invalid tracker config for %s: %s", DOMAIN, tracker)
            return False

        tracker_id = str(tracker.get(CONF_ID, DEFAULT_TRACKER_ID)).strip()
        tracker_name = str(tracker.get(CONF_NAME, tracker_id)).strip() or tracker_id
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
                    CONF_NAME: tracker_name,
                },
            )
        )

    return True


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Set up Dinner Attendance Tracker from a config entry."""
    from .manager import DinnerAttendanceManager

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


async def async_unload_entry(hass: Any, entry: Any) -> bool:
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
            SERVICE_SET_PERSON_DEFAULTS,
            SERVICE_SET_ATTENDANCE,
            SERVICE_CLEAR_DAY,
            SERVICE_RESET_WEEK,
        ):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
        domain_data[DATA_SERVICES_REGISTERED] = False

    return True


async def _ensure_card_registered(hass: Any) -> None:
    """Expose the bundled Lovelace card from inside the integration directory."""
    domain_data = _ensure_domain_data(hass)
    if domain_data[DATA_CARD_REGISTERED]:
        return

    try:
        from homeassistant.components.http import StaticPathConfig
    except ImportError:
        result = hass.http.async_register_static_path(
            CARD_URL_PATH,
            str(CARD_FILE_PATH),
            cache_headers=True,
        )
        if inspect.isawaitable(result):
            await result
    else:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_PATH, str(CARD_FILE_PATH), cache_headers=True)]
        )

    domain_data[DATA_CARD_REGISTERED] = True


def _resolve_manager(hass: Any, call_data: dict[str, Any]) -> Any:
    from homeassistant.exceptions import HomeAssistantError

    domain_data = _ensure_domain_data(hass)
    entries = domain_data[DATA_ENTRIES]

    entity_id = call_data.get(FIELD_ENTITY_ID)
    if entity_id:
        state = hass.states.get(str(entity_id))
        tracker_id = state.attributes.get("tracker_id") if state is not None else None
        if tracker_id:
            for entry_data in entries.values():
                manager = entry_data[DATA_MANAGER]
                if manager.tracker_id() == tracker_id:
                    return manager
        raise HomeAssistantError("Unknown tracker entity_id")

    if len(entries) == 1:
        return next(iter(entries.values()))[DATA_MANAGER]

    raise HomeAssistantError("Provide entity_id when more than one tracker exists")


def _register_services(hass: Any) -> None:
    import voluptuous as vol

    service_schema_add_person = vol.Schema(
        {
            vol.Optional(FIELD_ENTITY_ID): str,
            vol.Required(FIELD_PERSON_ENTITY_ID): str,
            vol.Optional(FIELD_NAME): str,
        }
    )
    service_schema_add_guest = vol.Schema(
        {
            vol.Optional(FIELD_ENTITY_ID): str,
            vol.Required(FIELD_NAME): str,
        }
    )
    service_schema_remove_participant = vol.Schema(
        {
            vol.Optional(FIELD_ENTITY_ID): str,
            vol.Required(FIELD_PARTICIPANT_ID): str,
        }
    )
    service_schema_set_person_defaults = vol.Schema(
        {
            vol.Optional(FIELD_ENTITY_ID): str,
            vol.Required(FIELD_PARTICIPANT_ID): str,
            vol.Optional(FIELD_DEFAULT_DINNER): vol.Coerce(bool),
            vol.Optional(FIELD_DEFAULT_OVERNIGHT): vol.Coerce(bool),
        }
    )
    service_schema_set_attendance = vol.Schema(
        {
            vol.Optional(FIELD_ENTITY_ID): str,
            vol.Required(FIELD_DAY): vol.In(DAY_KEYS),
            vol.Required(FIELD_PARTICIPANT_ID): str,
            vol.Optional(FIELD_DINNER): vol.Coerce(bool),
            vol.Optional(FIELD_OVERNIGHT): vol.Coerce(bool),
        }
    )
    service_schema_clear_day = vol.Schema(
        {
            vol.Optional(FIELD_ENTITY_ID): str,
            vol.Required(FIELD_DAY): vol.In(DAY_KEYS),
        }
    )
    service_schema_reset_week = vol.Schema({vol.Optional(FIELD_ENTITY_ID): str})

    async def handle_add_person(call: Any) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_add_person(
            str(call.data[FIELD_PERSON_ENTITY_ID]),
            name=call.data.get(FIELD_NAME),
        )

    async def handle_add_guest(call: Any) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_add_guest(str(call.data[FIELD_NAME]))

    async def handle_remove_participant(call: Any) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_remove_participant(str(call.data[FIELD_PARTICIPANT_ID]))

    async def handle_set_person_defaults(call: Any) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_set_person_defaults(
            str(call.data[FIELD_PARTICIPANT_ID]),
            default_dinner=call.data.get(FIELD_DEFAULT_DINNER),
            default_overnight=call.data.get(FIELD_DEFAULT_OVERNIGHT),
        )

    async def handle_set_attendance(call: Any) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_set_attendance(
            str(call.data[FIELD_DAY]),
            str(call.data[FIELD_PARTICIPANT_ID]),
            dinner=call.data.get(FIELD_DINNER),
            overnight=call.data.get(FIELD_OVERNIGHT),
        )

    async def handle_clear_day(call: Any) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_clear_day(str(call.data[FIELD_DAY]))

    async def handle_reset_week(call: Any) -> None:
        manager = _resolve_manager(hass, call.data)
        await manager.async_reset_week()

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PERSON,
        handle_add_person,
        schema=service_schema_add_person,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_GUEST,
        handle_add_guest,
        schema=service_schema_add_guest,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_PARTICIPANT,
        handle_remove_participant,
        schema=service_schema_remove_participant,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PERSON_DEFAULTS,
        handle_set_person_defaults,
        schema=service_schema_set_person_defaults,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ATTENDANCE,
        handle_set_attendance,
        schema=service_schema_set_attendance,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_DAY,
        handle_clear_day,
        schema=service_schema_clear_day,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_WEEK,
        handle_reset_week,
        schema=service_schema_reset_week,
    )
