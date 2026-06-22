"""Constants for the Dinner Attendance Tracker integration."""

DOMAIN = "dinner_attendance_tracker"
STORAGE_VERSION = 1
STORAGE_KEY = "dinner_attendance_tracker.storage"

DATA_ENTRIES = "entries"
DATA_MANAGER = "manager"
DATA_SERVICES_REGISTERED = "services_registered"
DATA_CARD_REGISTERED = "card_registered"

CONF_TRACKERS = "trackers"
CONF_ID = "id"
CONF_NAME = "name"

DEFAULT_TRACKER_ID = "dinner_attendance"
DEFAULT_TRACKER_NAME = "Dinner Attendance"

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_NAMES = {
    "mon": "Montag",
    "tue": "Dienstag",
    "wed": "Mittwoch",
    "thu": "Donnerstag",
    "fri": "Freitag",
    "sat": "Samstag",
    "sun": "Sonntag",
}

SERVICE_ADD_PERSON = "add_person"
SERVICE_ADD_GUEST = "add_guest"
SERVICE_REMOVE_PARTICIPANT = "remove_participant"
SERVICE_SET_ATTENDANCE = "set_attendance"
SERVICE_CLEAR_DAY = "clear_day"
SERVICE_RESET_WEEK = "reset_week"

FIELD_ENTITY_ID = "entity_id"
FIELD_PERSON_ENTITY_ID = "person_entity_id"
FIELD_NAME = "name"
FIELD_PARTICIPANT_ID = "participant_id"
FIELD_DAY = "day"
FIELD_DINNER = "dinner"
FIELD_OVERNIGHT = "overnight"

ATTR_TRACKER_ID = "tracker_id"
ATTR_TRACKER_TYPE = "tracker_type"
ATTR_PARTICIPANTS = "participants"
ATTR_DAYS = "days"
ATTR_TODAY = "today"
ATTR_TODAY_KEY = "today_key"
ATTR_DINNER_TODAY = "dinner_today"
ATTR_OVERNIGHT_TODAY = "overnight_today"
ATTR_DINNER_COUNT_TODAY = "dinner_count_today"
ATTR_OVERNIGHT_COUNT_TODAY = "overnight_count_today"

TRACKER_TYPE_DINNER_ATTENDANCE = "dinner_attendance"
PARTICIPANT_TYPE_PERSON = "person"
PARTICIPANT_TYPE_GUEST = "guest"
