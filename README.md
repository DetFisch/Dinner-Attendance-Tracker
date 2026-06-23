# Dinner Attendance Tracker

Home Assistant Custom Integration mit gebündelter Lovelace-Card für einen einfachen Wochenplan:

- alle sieben Wochentage sichtbar
- pro Tag getrennte Anzeige für Abendessen und Übernachtung
- Home Assistant `person`-Entities auswählbar
- zusätzliche Gäste als freie Namen
- Zustand wird in Home Assistant gespeichert, nicht nur im Browser

## Installation

1. Repository per HACS als `Integration` installieren oder `custom_components/dinner_attendance_tracker` nach `<HA_CONFIG>/custom_components/dinner_attendance_tracker` kopieren.
2. Home Assistant neu starten.
3. Integration hinzufügen: `Einstellungen` > `Geräte & Dienste` > `Integration hinzufügen` > `Dinner Attendance Tracker`. Es wird automatisch ein Tracker `dinner_attendance` angelegt.
4. Lovelace Resource hinzufügen:
   - URL: `/dinner_attendance_tracker/dinner-attendance-card.js?v=0.1.4`
   - Typ: `module`
5. Browser Hard-Reload (`Ctrl+F5`).

## Card-Konfiguration

Minimal, wenn nur ein Tracker existiert:

```yaml
type: custom:dinner-attendance-card
name: Abendessen
```

Explizit:

```yaml
type: custom:dinner-attendance-card
entity: sensor.dinner_attendance
name: Abendessen
```

Optional kann der Editor direkt geöffnet starten:

```yaml
type: custom:dinner-attendance-card
entity: sensor.dinner_attendance
name: Abendessen
editor_open: true
```

## Nutzung

Die Karte zeigt jeden Wochentag mit zwei Zeilen:

- Besteck: wer zum Abendessen da ist
- Bett: wer übernachtet

Über das Stift-Symbol oder einen Klick auf einen Wochentag öffnest du den Editor. Dort kannst du Home Assistant Personen hinzufügen, Gäste eintragen und pro Teilnehmer die beiden Toggles `Essen` und `Nacht` setzen.

## Services

Alle Services akzeptieren optional `entity_id`, falls mehrere Tracker existieren:

- `dinner_attendance_tracker.add_person`
- `dinner_attendance_tracker.add_guest`
- `dinner_attendance_tracker.remove_participant`
- `dinner_attendance_tracker.set_attendance`
- `dinner_attendance_tracker.clear_day`
- `dinner_attendance_tracker.reset_week`

Beispiel:

```yaml
service: dinner_attendance_tracker.set_attendance
data:
  entity_id: sensor.dinner_attendance
  day: fri
  participant_id: person.jon
  dinner: true
  overnight: false
```

## YAML-Import

Alternativ zur UI:

```yaml
dinner_attendance_tracker:
  id: dinner_attendance
  name: Abendessen
```

Mehrere Tracker:

```yaml
dinner_attendance_tracker:
  trackers:
    - id: dinner_attendance
      name: Abendessen
    - id: weekend_guests
      name: Wochenendgäste
```
