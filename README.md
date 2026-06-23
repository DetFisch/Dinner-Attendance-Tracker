# Dinner Attendance Tracker

Home Assistant Custom Integration mit gebündelter Lovelace-Card für einen einfachen Wochenplan:

- heute und die nächsten sechs Tage sichtbar
- pro Tag getrennte Anzeige für Abendessen und Übernachtung
- Home Assistant `person`-Entities auswählbar
- zusätzliche Gäste als freie Namen
- Zustand wird in Home Assistant gespeichert, nicht nur im Browser

## Installation

1. Repository per HACS als `Integration` installieren oder `custom_components/dinner_attendance_tracker` nach `<HA_CONFIG>/custom_components/dinner_attendance_tracker` kopieren.
2. Home Assistant neu starten.
3. Integration hinzufügen: `Einstellungen` > `Geräte & Dienste` > `Integration hinzufügen` > `Dinner Attendance Tracker`. Es wird automatisch ein Tracker `dinner_attendance` angelegt.
4. Lovelace Resource hinzufügen:
   - URL: `/dinner_attendance_tracker/dinner-attendance-card.js?v=0.2.7`
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

Optional mit `Ich`-Schnellzugriff und Standard-Anwesenheit direkt in YAML:

```yaml
type: custom:dinner-attendance-card
entity: sensor.dinner_attendance
name: Abendessen
me_entity: person.jon
default_dinner:
  - person.jon
  - person.alex
default_overnight:
  - person.jon
```

## Nutzung

Die Karte zeigt die nächsten sieben Tage ab heute mit zwei Zeilen:

- Besteck: wer zum Abendessen da ist
- Bett: wer übernachtet

Ein Klick auf einen Wochentag öffnet den Editor als Popup. Oben steht, falls konfiguriert, der `Ich`-Schnellzugriff. Darunter kannst du andere Home Assistant Personen und Gäste verwalten.

Wenn `Ich` nicht in YAML gesetzt ist, kannst du im Popup einmal eine Home Assistant Person als `Ich` für dieses Dashboard festlegen. Diese Auswahl wird lokal im Browser gespeichert.

Standardpersonen kannst du ebenfalls im Popup setzen:

- beim Hinzufügen einer Home Assistant Person die Checkboxen `Immer Essen` und `Immer Nacht` aktivieren
- bei bereits vorhandenen Personen die Buttons `Immer Essen` und `Immer Nacht` verwenden

Standardpersonen sind jede Woche automatisch eingetragen. Im Popup trägst du sie nur an Ausnahmetagen aus.

## Services

Alle Services akzeptieren optional `entity_id`, falls mehrere Tracker existieren:

- `dinner_attendance_tracker.add_person`
- `dinner_attendance_tracker.add_guest`
- `dinner_attendance_tracker.remove_participant`
- `dinner_attendance_tracker.set_person_defaults`
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
