"""Runtime state manager for Dinner Attendance Tracker."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    ATTR_DAYS,
    ATTR_DINNER_COUNT_TODAY,
    ATTR_DINNER_TODAY,
    ATTR_OVERNIGHT_COUNT_TODAY,
    ATTR_OVERNIGHT_TODAY,
    ATTR_PARTICIPANTS,
    ATTR_TODAY,
    ATTR_TODAY_KEY,
    CONF_ID,
    CONF_NAME,
    DAY_KEYS,
    DAY_NAMES,
    DEFAULT_TRACKER_NAME,
    DOMAIN,
    PARTICIPANT_TYPE_GUEST,
    PARTICIPANT_TYPE_PERSON,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class DinnerAttendanceManager(DataUpdateCoordinator[dict[str, Any]]):
    """Manage dinner attendance state and persistence."""

    def __init__(
        self,
        hass: HomeAssistant,
        tracker_id: str,
        tracker_name: str,
        storage_key: str | None = None,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            storage_key or STORAGE_KEY,
        )
        self._tracker_id = tracker_id
        self._tracker_name = tracker_name or DEFAULT_TRACKER_NAME
        self._data: dict[str, Any] = {}

    async def async_initialize(self) -> None:
        """Load persisted state and normalize it."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._data = stored

        changed = self._normalize()
        if changed:
            await self._save()

        self.async_set_updated_data(self._public_data())

    def tracker_id(self) -> str:
        """Return the configured tracker id."""
        return self._tracker_id

    def tracker_state(self) -> dict[str, Any]:
        """Return public tracker state."""
        return self._public_data()

    async def async_add_person(
        self,
        person_entity_id: str,
        name: str | None = None,
    ) -> None:
        """Add a Home Assistant person entity to the tracker."""
        if not person_entity_id.startswith("person."):
            raise HomeAssistantError("person_entity_id must be a person entity")

        participant_id = person_entity_id
        display_name = self._display_name_from_person(person_entity_id, name)
        participants = self._data[ATTR_PARTICIPANTS]

        for participant in participants:
            if participant.get("id") != participant_id:
                continue
            participant["name"] = display_name
            participant["entity_id"] = person_entity_id
            participant["type"] = PARTICIPANT_TYPE_PERSON
            await self._save_and_publish()
            return

        participants.append(
            {
                "id": participant_id,
                "type": PARTICIPANT_TYPE_PERSON,
                "name": display_name,
                "entity_id": person_entity_id,
            }
        )
        await self._save_and_publish()

    async def async_add_guest(self, name: str) -> None:
        """Add a custom guest entry."""
        display_name = self._normalize_name(name)
        if not display_name:
            raise HomeAssistantError("name is required")

        participants = self._data[ATTR_PARTICIPANTS]
        existing = next(
            (
                participant
                for participant in participants
                if participant.get("type") == PARTICIPANT_TYPE_GUEST
                and self._name_key(participant.get("name")) == self._name_key(display_name)
            ),
            None,
        )
        if existing is not None:
            await self._save_and_publish()
            return

        guest_slug = slugify(display_name) or "guest"
        participants.append(
            {
                "id": f"guest_{guest_slug}_{uuid4().hex[:6]}",
                "type": PARTICIPANT_TYPE_GUEST,
                "name": display_name,
            }
        )
        await self._save_and_publish()

    async def async_remove_participant(self, participant_id: str) -> None:
        """Remove a participant from the tracker and every day."""
        participants = self._data[ATTR_PARTICIPANTS]
        kept_participants = [
            participant
            for participant in participants
            if str(participant.get("id")) != participant_id
        ]
        if len(kept_participants) == len(participants):
            raise HomeAssistantError("participant_id not found")

        self._data[ATTR_PARTICIPANTS] = kept_participants
        for day in self._data[ATTR_DAYS].values():
            day["dinner"] = [
                current_id for current_id in day["dinner"] if current_id != participant_id
            ]
            day["overnight"] = [
                current_id
                for current_id in day["overnight"]
                if current_id != participant_id
            ]

        await self._save_and_publish()

    async def async_set_attendance(
        self,
        day_key: str,
        participant_id: str,
        dinner: bool | None = None,
        overnight: bool | None = None,
    ) -> None:
        """Set dinner and/or overnight attendance for one participant on one day."""
        day_key = self._normalize_day(day_key)
        if dinner is None and overnight is None:
            raise HomeAssistantError("Provide dinner or overnight")
        if participant_id not in self._participant_ids():
            raise HomeAssistantError("participant_id not found")

        day = self._data[ATTR_DAYS][day_key]
        if dinner is not None:
            self._set_membership(day["dinner"], participant_id, dinner)
        if overnight is not None:
            self._set_membership(day["overnight"], participant_id, overnight)

        self._sort_day_lists(day)
        await self._save_and_publish()

    async def async_clear_day(self, day_key: str) -> None:
        """Clear all attendance for one day."""
        day_key = self._normalize_day(day_key)
        self._data[ATTR_DAYS][day_key] = {"dinner": [], "overnight": []}
        await self._save_and_publish()

    async def async_reset_week(self) -> None:
        """Clear the whole weekly plan."""
        self._data[ATTR_DAYS] = self._empty_days()
        await self._save_and_publish()

    def _normalize(self) -> bool:
        changed = False

        if self._data.get(CONF_ID) != self._tracker_id:
            self._data[CONF_ID] = self._tracker_id
            changed = True
        if self._data.get(CONF_NAME) != self._tracker_name:
            self._data[CONF_NAME] = self._tracker_name
            changed = True

        participants = self._data.get(ATTR_PARTICIPANTS)
        if not isinstance(participants, list):
            self._data[ATTR_PARTICIPANTS] = []
            participants = self._data[ATTR_PARTICIPANTS]
            changed = True

        normalized_participants: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for participant in participants:
            if not isinstance(participant, dict):
                changed = True
                continue
            participant_id = str(participant.get("id", "")).strip()
            participant_type = str(participant.get("type", "")).strip()
            name = self._normalize_name(participant.get("name"))
            entity_id = str(participant.get("entity_id", "")).strip()

            if participant_type == PARTICIPANT_TYPE_PERSON:
                if not entity_id.startswith("person."):
                    entity_id = participant_id if participant_id.startswith("person.") else ""
                if not entity_id:
                    changed = True
                    continue
                participant_id = entity_id
                name = self._display_name_from_person(entity_id, name)
            elif participant_type != PARTICIPANT_TYPE_GUEST:
                participant_type = PARTICIPANT_TYPE_GUEST

            if not participant_id or not name or participant_id in seen_ids:
                changed = True
                continue

            normalized = {
                "id": participant_id,
                "type": participant_type,
                "name": name,
            }
            if participant_type == PARTICIPANT_TYPE_PERSON:
                normalized["entity_id"] = entity_id

            normalized_participants.append(normalized)
            seen_ids.add(participant_id)
            changed = changed or normalized != participant

        if normalized_participants != participants:
            self._data[ATTR_PARTICIPANTS] = normalized_participants
            changed = True

        days = self._data.get(ATTR_DAYS)
        if not isinstance(days, dict):
            self._data[ATTR_DAYS] = self._empty_days()
            return True

        known_ids = self._participant_ids()
        normalized_days: dict[str, dict[str, list[str]]] = {}
        for day_key in DAY_KEYS:
            day = days.get(day_key)
            if not isinstance(day, dict):
                normalized_days[day_key] = {"dinner": [], "overnight": []}
                changed = True
                continue

            normalized_day = {
                "dinner": self._normalize_member_list(day.get("dinner"), known_ids),
                "overnight": self._normalize_member_list(day.get("overnight"), known_ids),
            }
            self._sort_day_lists(normalized_day)
            normalized_days[day_key] = normalized_day
            changed = changed or normalized_day != day

        if normalized_days != days:
            self._data[ATTR_DAYS] = normalized_days
            changed = True

        return changed

    def _public_data(self) -> dict[str, Any]:
        participants = [self._public_participant(participant) for participant in self._data[ATTR_PARTICIPANTS]]
        participant_map = {participant["id"]: participant for participant in participants}
        days: dict[str, Any] = {}
        for day_key in DAY_KEYS:
            day = self._data[ATTR_DAYS][day_key]
            dinner = [participant_id for participant_id in day["dinner"] if participant_id in participant_map]
            overnight = [
                participant_id
                for participant_id in day["overnight"]
                if participant_id in participant_map
            ]
            days[day_key] = {
                "key": day_key,
                "name": DAY_NAMES[day_key],
                "dinner": dinner,
                "overnight": overnight,
                "dinner_names": [participant_map[item]["name"] for item in dinner],
                "overnight_names": [participant_map[item]["name"] for item in overnight],
                "dinner_count": len(dinner),
                "overnight_count": len(overnight),
            }

        today_key = self._today_key()
        today = days[today_key]
        return {
            CONF_ID: self._tracker_id,
            CONF_NAME: self._tracker_name,
            ATTR_PARTICIPANTS: participants,
            ATTR_DAYS: days,
            ATTR_TODAY_KEY: today_key,
            ATTR_TODAY: today,
            ATTR_DINNER_TODAY: today["dinner_names"],
            ATTR_OVERNIGHT_TODAY: today["overnight_names"],
            ATTR_DINNER_COUNT_TODAY: today["dinner_count"],
            ATTR_OVERNIGHT_COUNT_TODAY: today["overnight_count"],
        }

    def _public_participant(self, participant: dict[str, Any]) -> dict[str, Any]:
        if participant.get("type") == PARTICIPANT_TYPE_PERSON:
            entity_id = str(participant.get("entity_id", participant.get("id")))
            return {
                "id": entity_id,
                "type": PARTICIPANT_TYPE_PERSON,
                "name": self._display_name_from_person(entity_id, participant.get("name")),
                "entity_id": entity_id,
            }

        return {
            "id": str(participant.get("id", "")),
            "type": PARTICIPANT_TYPE_GUEST,
            "name": self._normalize_name(participant.get("name")),
        }

    def _display_name_from_person(self, entity_id: str, fallback: Any = None) -> str:
        state = self.hass.states.get(entity_id)
        if state is not None:
            friendly_name = state.attributes.get("friendly_name")
            if friendly_name:
                return self._normalize_name(friendly_name)
        fallback_name = self._normalize_name(fallback)
        if fallback_name:
            return fallback_name
        return entity_id.removeprefix("person.").replace("_", " ").title()

    def _participant_ids(self) -> set[str]:
        return {
            str(participant.get("id"))
            for participant in self._data.get(ATTR_PARTICIPANTS, [])
            if isinstance(participant, dict)
        }

    def _normalize_member_list(self, raw_value: Any, known_ids: set[str]) -> list[str]:
        if not isinstance(raw_value, list):
            return []

        normalized = []
        for item in raw_value:
            participant_id = str(item)
            if participant_id not in known_ids or participant_id in normalized:
                continue
            normalized.append(participant_id)
        return normalized

    def _sort_day_lists(self, day: dict[str, list[str]]) -> None:
        order = {
            str(participant.get("id")): index
            for index, participant in enumerate(self._data[ATTR_PARTICIPANTS])
            if isinstance(participant, dict)
        }
        day["dinner"].sort(key=lambda participant_id: order.get(participant_id, 9999))
        day["overnight"].sort(key=lambda participant_id: order.get(participant_id, 9999))

    async def _save_and_publish(self) -> None:
        self._normalize()
        await self._save()
        self.async_set_updated_data(self._public_data())

    async def _save(self) -> None:
        await self._store.async_save(self._data)

    @staticmethod
    def _empty_days() -> dict[str, dict[str, list[str]]]:
        return {day_key: {"dinner": [], "overnight": []} for day_key in DAY_KEYS}

    @staticmethod
    def _set_membership(items: list[str], participant_id: str, enabled: bool) -> None:
        if enabled and participant_id not in items:
            items.append(participant_id)
        if not enabled and participant_id in items:
            items.remove(participant_id)

    @staticmethod
    def _normalize_day(day_key: str) -> str:
        normalized = str(day_key).lower().strip()
        if normalized not in DAY_KEYS:
            raise HomeAssistantError("day must be one of mon, tue, wed, thu, fri, sat, sun")
        return normalized

    @staticmethod
    def _normalize_name(name: Any) -> str:
        if name is None:
            return ""
        return " ".join(str(name).split())[:80]

    @staticmethod
    def _name_key(name: Any) -> str:
        return " ".join(str(name).split()).casefold()

    @staticmethod
    def _today_key() -> str:
        return DAY_KEYS[dt_util.now().weekday()]
