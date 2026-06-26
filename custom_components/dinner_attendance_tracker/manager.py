"""Runtime state manager for Dinner Attendance Tracker."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    ATTR_DEFAULT_DINNER,
    ATTR_DEFAULT_OVERNIGHT,
    ATTR_DAYS,
    ATTR_DINNER_ABSENT,
    ATTR_DINNER_COUNT_TODAY,
    ATTR_DINNER_TODAY,
    ATTR_OVERNIGHT_ABSENT,
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
        self._unsub_date_refresh = None

    async def async_initialize(self) -> None:
        """Load persisted state and normalize it."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._data = stored

        changed = self._normalize()
        if changed:
            await self._save()

        self.async_set_updated_data(self._public_data())
        self._schedule_date_refresh()

    def tracker_id(self) -> str:
        """Return the configured tracker id."""
        return self._tracker_id

    def tracker_state(self) -> dict[str, Any]:
        """Return public tracker state."""
        return self._public_data()

    def async_shutdown(self) -> None:
        """Stop scheduled callbacks."""
        if self._unsub_date_refresh is not None:
            self._unsub_date_refresh()
            self._unsub_date_refresh = None

    async def async_add_person(
        self,
        person_entity_id: str,
        name: str | None = None,
        default_dinner: bool | None = None,
        default_overnight: bool | None = None,
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
            if default_dinner is not None:
                participant[ATTR_DEFAULT_DINNER] = bool(default_dinner)
            if default_overnight is not None:
                participant[ATTR_DEFAULT_OVERNIGHT] = bool(default_overnight)
            await self._save_and_publish()
            return

        participant = {
            "id": participant_id,
            "type": PARTICIPANT_TYPE_PERSON,
            "name": display_name,
            "entity_id": person_entity_id,
            ATTR_DEFAULT_DINNER: bool(default_dinner) if default_dinner is not None else False,
            ATTR_DEFAULT_OVERNIGHT: bool(default_overnight) if default_overnight is not None else False,
        }
        participants.append(participant)
        await self._save_and_publish()

    async def async_set_person_defaults(
        self,
        participant_id: str,
        default_dinner: bool | None = None,
        default_overnight: bool | None = None,
    ) -> None:
        """Set weekly default attendance for a person participant."""
        participant = self._get_participant(participant_id)
        if participant.get("type") != PARTICIPANT_TYPE_PERSON:
            raise HomeAssistantError("defaults are only supported for person participants")
        if default_dinner is None and default_overnight is None:
            raise HomeAssistantError("Provide default_dinner or default_overnight")

        if default_dinner is not None:
            participant[ATTR_DEFAULT_DINNER] = bool(default_dinner)
        if default_overnight is not None:
            participant[ATTR_DEFAULT_OVERNIGHT] = bool(default_overnight)

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
        """Remove a participant from the tracker and every stored date."""
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
        date_key: str | None = None,
    ) -> None:
        """Set dinner and/or overnight attendance for one participant on one date."""
        day_key = self._normalize_day(day_key)
        date_key = self._normalize_or_resolve_date(date_key, day_key)
        if dinner is None and overnight is None:
            raise HomeAssistantError("Provide dinner or overnight")
        if participant_id not in self._participant_ids():
            raise HomeAssistantError("participant_id not found")

        day = self._data[ATTR_DAYS].setdefault(date_key, self._empty_day())
        if dinner is not None:
            self._set_attendance_membership(
                day,
                participant_id,
                present=bool(dinner),
                default_key=ATTR_DEFAULT_DINNER,
                present_key="dinner",
                absent_key=ATTR_DINNER_ABSENT,
            )
        if overnight is not None:
            self._set_attendance_membership(
                day,
                participant_id,
                present=bool(overnight),
                default_key=ATTR_DEFAULT_OVERNIGHT,
                present_key="overnight",
                absent_key=ATTR_OVERNIGHT_ABSENT,
            )

        self._sort_day_lists(day)
        await self._save_and_publish()

    async def async_clear_day(self, day_key: str, date_key: str | None = None) -> None:
        """Clear all attendance overrides for one date."""
        day_key = self._normalize_day(day_key)
        date_key = self._normalize_or_resolve_date(date_key, day_key)
        self._data[ATTR_DAYS].pop(date_key, None)
        await self._save_and_publish()

    async def async_reset_week(self) -> None:
        """Clear the visible rolling seven-day plan."""
        for date_key in self._visible_date_keys():
            self._data[ATTR_DAYS].pop(date_key, None)
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
                ATTR_DEFAULT_DINNER: bool(participant.get(ATTR_DEFAULT_DINNER, False)),
                ATTR_DEFAULT_OVERNIGHT: bool(participant.get(ATTR_DEFAULT_OVERNIGHT, False)),
            }
            if participant_type == PARTICIPANT_TYPE_PERSON:
                normalized["entity_id"] = entity_id
            else:
                normalized[ATTR_DEFAULT_DINNER] = False
                normalized[ATTR_DEFAULT_OVERNIGHT] = False

            normalized_participants.append(normalized)
            seen_ids.add(participant_id)
            changed = changed or normalized != participant

        if normalized_participants != participants:
            self._data[ATTR_PARTICIPANTS] = normalized_participants
            changed = True

        days = self._data.get(ATTR_DAYS)
        if not isinstance(days, dict):
            self._data[ATTR_DAYS] = {}
            return True

        known_ids = self._participant_ids()
        normalized_days: dict[str, dict[str, list[str]]] = {}
        for raw_key, day in days.items():
            if not isinstance(day, dict):
                changed = True
                continue

            date_key = self._normalize_date_key(raw_key)
            if date_key is None:
                day_key = str(raw_key).lower().strip()
                if day_key not in DAY_KEYS:
                    changed = True
                    continue
                date_key = self._date_key_for_current_weekday(day_key)

            normalized_day = {
                "dinner": self._normalize_member_list(day.get("dinner"), known_ids),
                "overnight": self._normalize_member_list(day.get("overnight"), known_ids),
                ATTR_DINNER_ABSENT: self._normalize_member_list(
                    day.get(ATTR_DINNER_ABSENT),
                    known_ids,
                ),
                ATTR_OVERNIGHT_ABSENT: self._normalize_member_list(
                    day.get(ATTR_OVERNIGHT_ABSENT),
                    known_ids,
                ),
            }
            self._sort_day_lists(normalized_day)
            if date_key in normalized_days:
                self._merge_day(normalized_days[date_key], normalized_day)
            else:
                normalized_days[date_key] = normalized_day
            changed = changed or date_key != raw_key or normalized_day != day

        pruned_days = self._prune_days(normalized_days)
        if pruned_days != days:
            self._data[ATTR_DAYS] = pruned_days
            changed = True

        return changed

    def _public_data(self) -> dict[str, Any]:
        participants = [self._public_participant(participant) for participant in self._data[ATTR_PARTICIPANTS]]
        participant_map = {participant["id"]: participant for participant in participants}
        days: dict[str, Any] = {}
        for date_key in self._visible_date_keys():
            days[date_key] = self._public_day(date_key, participant_map)

        today_date = self._today_date_key()
        today = days[today_date]
        return {
            CONF_ID: self._tracker_id,
            CONF_NAME: self._tracker_name,
            ATTR_PARTICIPANTS: participants,
            ATTR_DAYS: days,
            ATTR_TODAY_KEY: today["key"],
            ATTR_TODAY: today,
            ATTR_DINNER_TODAY: today["dinner_names"],
            ATTR_OVERNIGHT_TODAY: today["overnight_names"],
            ATTR_DINNER_COUNT_TODAY: today["dinner_count"],
            ATTR_OVERNIGHT_COUNT_TODAY: today["overnight_count"],
        }

    def _public_day(
        self,
        date_key: str,
        participant_map: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        day = self._data[ATTR_DAYS].get(date_key, self._empty_day())
        day_date = self._date_from_key(date_key)
        day_key = DAY_KEYS[day_date.weekday()]
        dinner = self._public_attendance_ids(
            day,
            participant_map,
            present_key="dinner",
            absent_key=ATTR_DINNER_ABSENT,
            default_key=ATTR_DEFAULT_DINNER,
        )
        overnight = self._public_attendance_ids(
            day,
            participant_map,
            present_key="overnight",
            absent_key=ATTR_OVERNIGHT_ABSENT,
            default_key=ATTR_DEFAULT_OVERNIGHT,
        )
        return {
            "date": date_key,
            "key": day_key,
            "name": DAY_NAMES[day_key],
            "dinner": dinner,
            "overnight": overnight,
            ATTR_DINNER_ABSENT: [
                participant_id
                for participant_id in day.get(ATTR_DINNER_ABSENT, [])
                if participant_id in participant_map
            ],
            ATTR_OVERNIGHT_ABSENT: [
                participant_id
                for participant_id in day.get(ATTR_OVERNIGHT_ABSENT, [])
                if participant_id in participant_map
            ],
            "dinner_names": [participant_map[item]["name"] for item in dinner],
            "overnight_names": [participant_map[item]["name"] for item in overnight],
            "dinner_count": len(dinner),
            "overnight_count": len(overnight),
        }

    def _public_participant(self, participant: dict[str, Any]) -> dict[str, Any]:
        if participant.get("type") == PARTICIPANT_TYPE_PERSON:
            entity_id = str(participant.get("entity_id", participant.get("id")))
            return {
                "id": entity_id,
                "type": PARTICIPANT_TYPE_PERSON,
                "name": self._display_name_from_person(entity_id, participant.get("name")),
                "entity_id": entity_id,
                ATTR_DEFAULT_DINNER: bool(participant.get(ATTR_DEFAULT_DINNER, False)),
                ATTR_DEFAULT_OVERNIGHT: bool(participant.get(ATTR_DEFAULT_OVERNIGHT, False)),
            }

        return {
            "id": str(participant.get("id", "")),
            "type": PARTICIPANT_TYPE_GUEST,
            "name": self._normalize_name(participant.get("name")),
            ATTR_DEFAULT_DINNER: False,
            ATTR_DEFAULT_OVERNIGHT: False,
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

    def _get_participant(self, participant_id: str) -> dict[str, Any]:
        for participant in self._data.get(ATTR_PARTICIPANTS, []):
            if isinstance(participant, dict) and str(participant.get("id")) == participant_id:
                return participant
        raise HomeAssistantError("participant_id not found")

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
        for key in ("dinner", "overnight", ATTR_DINNER_ABSENT, ATTR_OVERNIGHT_ABSENT):
            day.setdefault(key, [])
            day[key].sort(key=lambda participant_id: order.get(participant_id, 9999))

    async def _save_and_publish(self) -> None:
        self._normalize()
        await self._save()
        self.async_set_updated_data(self._public_data())

    async def _save(self) -> None:
        await self._store.async_save(self._data)

    def _schedule_date_refresh(self) -> None:
        if self._unsub_date_refresh is not None:
            self._unsub_date_refresh()
        now = dt_util.now()
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0,
            minute=0,
            second=1,
            microsecond=0,
        )
        delay = max(1, (next_midnight - now).total_seconds())
        self._unsub_date_refresh = async_call_later(
            self.hass,
            delay,
            self._handle_date_refresh,
        )

    def _handle_date_refresh(self, _now: Any) -> None:
        self.async_set_updated_data(self._public_data())
        self._schedule_date_refresh()

    @staticmethod
    def _empty_day() -> dict[str, list[str]]:
        return {
            "dinner": [],
            "overnight": [],
            ATTR_DINNER_ABSENT: [],
            ATTR_OVERNIGHT_ABSENT: [],
        }

    @classmethod
    def _empty_days(cls) -> dict[str, dict[str, list[str]]]:
        return {}

    def _merge_day(
        self,
        target: dict[str, list[str]],
        source: dict[str, list[str]],
    ) -> None:
        for key in ("dinner", "overnight", ATTR_DINNER_ABSENT, ATTR_OVERNIGHT_ABSENT):
            for participant_id in source.get(key, []):
                self._set_membership(target.setdefault(key, []), participant_id, True)
        self._sort_day_lists(target)

    def _normalize_or_resolve_date(self, date_key: Any, day_key: str) -> str:
        if date_key:
            normalized = self._normalize_date_key(date_key)
            if normalized is None:
                raise HomeAssistantError("date must be YYYY-MM-DD")
            normalized_day = DAY_KEYS[self._date_from_key(normalized).weekday()]
            if normalized_day != day_key:
                raise HomeAssistantError("date does not match day")
            return normalized
        return self._date_key_for_current_weekday(day_key)

    @staticmethod
    def _normalize_date_key(raw_key: Any) -> str | None:
        try:
            return date.fromisoformat(str(raw_key).strip()).isoformat()
        except ValueError:
            return None

    @staticmethod
    def _date_from_key(date_key: str) -> date:
        return date.fromisoformat(date_key)

    def _date_key_for_current_weekday(self, day_key: str) -> str:
        today = dt_util.now().date()
        monday = today - timedelta(days=today.weekday())
        return (monday + timedelta(days=DAY_KEYS.index(day_key))).isoformat()

    def _visible_date_keys(self) -> list[str]:
        today = dt_util.now().date()
        return [(today + timedelta(days=offset)).isoformat() for offset in range(7)]

    def _today_date_key(self) -> str:
        return dt_util.now().date().isoformat()

    def _prune_days(
        self,
        days: dict[str, dict[str, list[str]]],
    ) -> dict[str, dict[str, list[str]]]:
        today = dt_util.now().date()
        earliest = today - timedelta(days=14)
        latest = today + timedelta(days=90)
        pruned: dict[str, dict[str, list[str]]] = {}
        for date_key, day in days.items():
            day_date = self._date_from_key(date_key)
            if earliest <= day_date <= latest:
                pruned[date_key] = day
        return pruned

    def _set_attendance_membership(
        self,
        day: dict[str, list[str]],
        participant_id: str,
        present: bool,
        default_key: str,
        present_key: str,
        absent_key: str,
    ) -> None:
        participant = self._get_participant(participant_id)
        has_default = bool(participant.get(default_key, False))

        if has_default:
            self._set_membership(day.setdefault(absent_key, []), participant_id, not present)
            self._set_membership(day.setdefault(present_key, []), participant_id, False)
            return

        self._set_membership(day.setdefault(present_key, []), participant_id, present)
        self._set_membership(day.setdefault(absent_key, []), participant_id, False)

    def _public_attendance_ids(
        self,
        day: dict[str, list[str]],
        participant_map: dict[str, dict[str, Any]],
        present_key: str,
        absent_key: str,
        default_key: str,
    ) -> list[str]:
        absent_ids = set(day.get(absent_key, []))
        public_ids: list[str] = []

        for participant_id, participant in participant_map.items():
            if bool(participant.get(default_key, False)) and participant_id not in absent_ids:
                public_ids.append(participant_id)

        for participant_id in day.get(present_key, []):
            if participant_id in participant_map and participant_id not in public_ids:
                public_ids.append(participant_id)

        return public_ids

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
