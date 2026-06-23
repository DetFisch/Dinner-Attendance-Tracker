const DAT_DOMAIN = "dinner_attendance_tracker"
const DAT_CARD_VERSION = "0.1.3"
const DAT_DEFAULT_TITLE = "Dinner Attendance"
const DAT_DAYS = [
  { key: "mon", short: "Mo", name: "Montag" },
  { key: "tue", short: "Di", name: "Dienstag" },
  { key: "wed", short: "Mi", name: "Mittwoch" },
  { key: "thu", short: "Do", name: "Donnerstag" },
  { key: "fri", short: "Fr", name: "Freitag" },
  { key: "sat", short: "Sa", name: "Samstag" },
  { key: "sun", short: "So", name: "Sonntag" }
]

class DinnerAttendanceCard extends HTMLElement {
  setConfig(config) {
    this._config = {
      name: config.name || DAT_DEFAULT_TITLE,
      entity: config.entity || null
    }
    this._selectedDay = this._isDayKey(config.default_day)
      ? config.default_day
      : this._isDayKey(this._selectedDay)
        ? this._selectedDay
        : null
    this._editorOpen = Boolean(config.editor_open)
  }

  set hass(hass) {
    this._hass = hass

    if (!this._root) {
      this._renderSkeleton()
      this._attachEvents()
    }

    this._syncEntity()
    this._renderState()
  }

  getCardSize() {
    return 5
  }

  _renderSkeleton() {
    this.innerHTML = `
      <style>
        :host {
          display: block;
        }

        ha-card {
          overflow: hidden;
        }

        .card-wrap {
          display: grid;
          gap: 12px;
        }

        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }

        .title {
          min-width: 0;
          color: var(--primary-text-color);
          font-size: 1.05rem;
          font-weight: 600;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .header-actions {
          display: flex;
          align-items: center;
          gap: 6px;
          flex: 0 0 auto;
        }

        button {
          box-sizing: border-box;
          border: 1px solid var(--divider-color);
          border-radius: var(--ha-border-radius-md, 8px);
          background: var(--card-background-color);
          color: var(--primary-text-color);
          font: inherit;
          cursor: pointer;
        }

        button:hover {
          background: var(--secondary-background-color);
        }

        button[disabled] {
          opacity: 0.45;
          cursor: default;
        }

        .icon-button {
          width: 36px;
          height: 36px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0;
        }

        .week {
          display: grid;
          border: 1px solid var(--divider-color);
          border-radius: var(--ha-card-border-radius, 8px);
          overflow: hidden;
        }

        .day-row {
          display: grid;
          grid-template-columns: 44px minmax(0, 1fr);
          gap: 10px;
          align-items: stretch;
          border: 0;
          border-bottom: 1px solid var(--divider-color);
          background: transparent;
          text-align: left;
          padding: 0;
          border-radius: 0;
        }

        .day-row:last-child {
          border-bottom: 0;
        }

        .day-row:hover,
        .day-row.selected {
          background: var(--secondary-background-color);
        }

        .day-label {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 58px;
          border-right: 1px solid var(--divider-color);
          font-weight: 700;
          color: var(--primary-text-color);
        }

        .day-lines {
          display: grid;
          gap: 6px;
          min-width: 0;
          padding: 8px 10px 8px 0;
        }

        .line {
          display: grid;
          grid-template-columns: 22px minmax(0, 1fr);
          align-items: center;
          gap: 8px;
          min-width: 0;
        }

        .line ha-icon {
          width: 18px;
          height: 18px;
          color: var(--secondary-text-color);
        }

        .chip-row {
          display: flex;
          align-items: center;
          gap: 6px;
          min-width: 0;
          flex-wrap: wrap;
        }

        .chip {
          display: inline-flex;
          align-items: center;
          max-width: 100%;
          min-height: 22px;
          padding: 1px 8px;
          border-radius: var(--ha-border-radius-pill, 999px);
          font-size: 0.82rem;
          line-height: 1.3;
          color: var(--primary-text-color);
          background: var(--secondary-background-color);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .chip.dinner {
          background: rgba(67, 160, 71, 0.16);
          background: color-mix(in srgb, var(--success-color, #43a047) 18%, transparent);
        }

        .chip.overnight {
          background: rgba(3, 155, 229, 0.16);
          background: color-mix(in srgb, var(--info-color, #039be5) 18%, transparent);
        }

        .empty {
          color: var(--secondary-text-color);
          font-size: 0.82rem;
        }

        .editor {
          display: grid;
          gap: 12px;
          border-top: 1px solid var(--divider-color);
          padding-top: 12px;
        }

        .editor[hidden] {
          display: none;
        }

        .editor-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }

        .editor-title {
          color: var(--primary-text-color);
          font-size: 0.95rem;
          font-weight: 600;
        }

        .participant-list {
          display: grid;
          gap: 6px;
        }

        .participant-row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto auto;
          gap: 8px;
          align-items: center;
          min-height: 42px;
          border: 1px solid var(--divider-color);
          border-radius: var(--ha-card-border-radius, 8px);
          padding: 6px;
        }

        .participant-name {
          min-width: 0;
          padding-left: 4px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: var(--primary-text-color);
        }

        .toggle-group {
          display: inline-flex;
          gap: 4px;
          align-items: center;
        }

        .toggle {
          min-width: 42px;
          height: 30px;
          padding: 0 8px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          color: var(--secondary-text-color);
        }

        .toggle ha-icon {
          width: 17px;
          height: 17px;
        }

        .toggle[aria-pressed="true"][data-attendance-action="dinner"] {
          border-color: var(--success-color, #43a047);
          background: rgba(67, 160, 71, 0.22);
          background: color-mix(in srgb, var(--success-color, #43a047) 24%, transparent);
          color: var(--primary-text-color);
        }

        .toggle[aria-pressed="true"][data-attendance-action="overnight"] {
          border-color: var(--info-color, #039be5);
          background: rgba(3, 155, 229, 0.22);
          background: color-mix(in srgb, var(--info-color, #039be5) 24%, transparent);
          color: var(--primary-text-color);
        }

        .remove-button {
          width: 30px;
          height: 30px;
          padding: 0;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          color: var(--secondary-text-color);
        }

        .remove-button ha-icon {
          width: 17px;
          height: 17px;
        }

        .add-grid {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 8px;
          align-items: end;
        }

        .field {
          display: grid;
          gap: 4px;
          min-width: 0;
        }

        .field span {
          color: var(--secondary-text-color);
          font-size: 0.78rem;
        }

        select,
        input {
          box-sizing: border-box;
          width: 100%;
          min-width: 0;
          min-height: 36px;
          border: 1px solid var(--divider-color);
          border-radius: var(--ha-border-radius-md, 8px);
          padding: 6px 10px;
          background: var(--ha-color-form-background, var(--card-background-color));
          color: var(--primary-text-color);
          font: inherit;
          outline: none;
        }

        select:focus,
        input:focus {
          border-color: var(--primary-color);
          box-shadow: 0 0 0 1px var(--primary-color);
        }

        .text-button {
          min-height: 36px;
          padding: 0 12px;
          white-space: nowrap;
        }

        .danger {
          color: var(--error-color);
        }

        .status {
          min-height: 18px;
          color: var(--secondary-text-color);
          font-size: 0.82rem;
        }

        .status.error {
          color: var(--error-color);
        }

        .message {
          color: var(--secondary-text-color);
          font-size: 0.9rem;
          line-height: 1.4;
        }

        @media (max-width: 520px) {
          .participant-row {
            grid-template-columns: minmax(0, 1fr) auto;
          }

          .toggle-group {
            grid-column: 1 / -1;
            justify-self: stretch;
            display: grid;
            grid-template-columns: 1fr 1fr;
          }

          .toggle {
            width: 100%;
          }

          .remove-button {
            grid-column: 2;
            grid-row: 1;
          }

          .add-grid {
            grid-template-columns: 1fr;
          }

          .text-button {
            width: 100%;
          }
        }
      </style>

      <ha-card>
        <div class="card-content card-wrap">
          <div class="header">
            <div id="title" class="title"></div>
            <div class="header-actions">
              <button id="toggle-editor" class="icon-button" title="Bearbeiten" aria-label="Bearbeiten">
                <ha-icon icon="mdi:pencil"></ha-icon>
              </button>
            </div>
          </div>
          <div id="content"></div>
          <div id="editor" class="editor" hidden></div>
          <div id="status" class="status"></div>
        </div>
      </ha-card>
    `

    this._root = this.querySelector("ha-card")
    this._content = this.querySelector("#content")
    this._editor = this.querySelector("#editor")
    this._status = this.querySelector("#status")
  }

  _attachEvents() {
    this.addEventListener("click", (event) => {
      const target = event.target
      if (!(target instanceof Element)) {
        return
      }

      const toggleEditor = target.closest("#toggle-editor")
      if (toggleEditor) {
        this._editorOpen = !this._editorOpen
        if (!this._selectedDay) {
          this._selectedDay = this._todayKey()
        }
        this._renderState()
        return
      }

      const dayRow = target.closest("[data-day-row]")
      if (dayRow) {
        this._selectedDay = dayRow.getAttribute("data-day-row")
        this._editorOpen = true
        this._renderState()
        return
      }

      const toggle = target.closest("[data-attendance-action]")
      if (toggle) {
        this._handleToggle(toggle)
        return
      }

      const remove = target.closest("[data-remove-participant]")
      if (remove) {
        this._handleRemoveParticipant(remove.getAttribute("data-remove-participant"))
        return
      }

      const clearDay = target.closest("[data-clear-day]")
      if (clearDay) {
        this._handleClearDay()
        return
      }

      const resetWeek = target.closest("[data-reset-week]")
      if (resetWeek) {
        this._handleResetWeek()
        return
      }

      const addPerson = target.closest("[data-add-person]")
      if (addPerson) {
        this._handleAddPerson()
        return
      }

      const addGuest = target.closest("[data-add-guest]")
      if (addGuest) {
        this._handleAddGuest()
      }
    })

    this.addEventListener("keydown", (event) => {
      const target = event.target
      if (!(target instanceof HTMLInputElement)) {
        return
      }
      if (event.key === "Enter" && target.id === "guest-name") {
        event.preventDefault()
        this._handleAddGuest()
      }
    })
  }

  _syncEntity() {
    this._multipleCandidates = false
    if (this._config.entity && this._hass?.states?.[this._config.entity]) {
      return
    }

    const candidates = Object.entries(this._hass?.states || {})
      .filter(([, state]) => state?.attributes?.tracker_type === "dinner_attendance")
      .map(([entityId]) => entityId)

    if (!this._config.entity && candidates.length === 1) {
      this._config.entity = candidates[0]
    } else if (!this._config.entity && candidates.length > 1) {
      this._multipleCandidates = true
    }
  }

  _renderState() {
    this.querySelector("#title").textContent = this._config.name || DAT_DEFAULT_TITLE

    const state = this._trackerState()
    if (!state) {
      this._content.innerHTML = this._missingMessage()
      this._editor.hidden = true
      return
    }

    const participants = this._participants()
    if (!this._selectedDay) {
      this._selectedDay = this._todayKey()
    }

    this._content.innerHTML = this._renderWeek()
    this._renderEditor(participants)
  }

  _renderWeek() {
    const days = this._days()
    return `
      <div class="week">
        ${DAT_DAYS.map((day) => this._renderDayRow(day, days[day.key])).join("")}
      </div>
    `
  }

  _renderDayRow(day, dayState) {
    const dinnerNames = Array.isArray(dayState?.dinner_names) ? dayState.dinner_names : []
    const overnightNames = Array.isArray(dayState?.overnight_names) ? dayState.overnight_names : []
    const selected = this._selectedDay === day.key ? " selected" : ""

    return `
      <button class="day-row${selected}" data-day-row="${day.key}" type="button">
        <span class="day-label">${day.short}</span>
        <span class="day-lines">
          <span class="line">
            <ha-icon icon="mdi:silverware-fork-knife" title="Abendessen"></ha-icon>
            <span class="chip-row">${this._chips(dinnerNames, "dinner")}</span>
          </span>
          <span class="line">
            <ha-icon icon="mdi:bed" title="Übernachtung"></ha-icon>
            <span class="chip-row">${this._chips(overnightNames, "overnight")}</span>
          </span>
        </span>
      </button>
    `
  }

  _renderEditor(participants) {
    const showEditor = this._editorOpen || participants.length === 0
    this._editor.hidden = !showEditor
    if (!showEditor) {
      return
    }

    const day = DAT_DAYS.find((item) => item.key === this._selectedDay) || DAT_DAYS[0]
    const dayState = this._days()[day.key] || { dinner: [], overnight: [] }
    const personOptions = this._personOptions(participants)

    this._editor.innerHTML = `
      <div class="editor-head">
        <div class="editor-title">${day.name}</div>
        <button class="text-button" data-clear-day type="button">Tag leeren</button>
      </div>

      <div class="participant-list">
        ${participants.length ? participants.map((participant) => (
          this._renderParticipantRow(participant, dayState)
        )).join("") : '<div class="message">Noch keine Personen oder Gäste.</div>'}
      </div>

      <div class="add-grid">
        <label class="field">
          <span>Home Assistant Person</span>
          <select id="person-select">
            ${personOptions.length
              ? '<option value="">Person wählen...</option>' + personOptions.map((person) => (
                `<option value="${this._escapeAttr(person.entityId)}">${this._escapeHtml(person.name)}</option>`
              )).join("")
              : '<option value="">Keine weiteren Personen</option>'}
          </select>
        </label>
        <button class="text-button" data-add-person type="button" ${personOptions.length ? "" : "disabled"}>Hinzufügen</button>
      </div>

      <div class="add-grid">
        <label class="field">
          <span>Gast</span>
          <input id="guest-name" type="text" autocomplete="off" placeholder="Name">
        </label>
        <button class="text-button" data-add-guest type="button">Hinzufügen</button>
      </div>

      <div class="editor-head">
        <span></span>
        <button class="text-button danger" data-reset-week type="button">Woche leeren</button>
      </div>
    `
  }

  _renderParticipantRow(participant, dayState) {
    const participantId = String(participant.id)
    const dinner = Array.isArray(dayState.dinner) && dayState.dinner.includes(participantId)
    const overnight = Array.isArray(dayState.overnight) && dayState.overnight.includes(participantId)
    const escapedId = this._escapeAttr(participantId)
    const escapedName = this._escapeHtml(participant.name)

    return `
      <div class="participant-row">
        <div class="participant-name" title="${this._escapeAttr(participant.name)}">${escapedName}</div>
        <div class="toggle-group">
          <button
            class="toggle"
            data-attendance-action="dinner"
            data-participant-id="${escapedId}"
            aria-pressed="${dinner ? "true" : "false"}"
            title="Abendessen"
            type="button"
          >
            <ha-icon icon="mdi:silverware-fork-knife"></ha-icon>
            Essen
          </button>
          <button
            class="toggle"
            data-attendance-action="overnight"
            data-participant-id="${escapedId}"
            aria-pressed="${overnight ? "true" : "false"}"
            title="Übernachtung"
            type="button"
          >
            <ha-icon icon="mdi:bed"></ha-icon>
            Nacht
          </button>
        </div>
        <button
          class="remove-button"
          data-remove-participant="${escapedId}"
          title="Entfernen"
          aria-label="Entfernen"
          type="button"
        >
          <ha-icon icon="mdi:close"></ha-icon>
        </button>
      </div>
    `
  }

  _chips(names, type) {
    if (!names.length) {
      return '<span class="empty">Niemand</span>'
    }

    return names.map((name) => (
      `<span class="chip ${type}" title="${this._escapeAttr(name)}">${this._escapeHtml(name)}</span>`
    )).join("")
  }

  async _handleToggle(toggle) {
    const participantId = toggle.getAttribute("data-participant-id")
    const action = toggle.getAttribute("data-attendance-action")
    if (!participantId || !action || !this._selectedDay) {
      return
    }

    const enabled = toggle.getAttribute("aria-pressed") !== "true"
    await this._callService("set_attendance", {
      day: this._selectedDay,
      participant_id: participantId,
      [action]: enabled
    })
  }

  async _handleAddPerson() {
    const select = this.querySelector("#person-select")
    const personEntityId = String(select?.value || "").trim()
    if (!personEntityId) {
      this._setStatus("Bitte eine Person auswählen.", true)
      return
    }

    await this._callService("add_person", { person_entity_id: personEntityId })
    if (select) {
      select.value = ""
    }
  }

  async _handleAddGuest() {
    const input = this.querySelector("#guest-name")
    const name = String(input?.value || "").trim().replace(/\s+/g, " ")
    if (!name) {
      this._setStatus("Bitte einen Namen eingeben.", true)
      return
    }

    await this._callService("add_guest", { name })
    if (input) {
      input.value = ""
    }
  }

  async _handleRemoveParticipant(participantId) {
    if (!participantId) {
      return
    }
    await this._callService("remove_participant", { participant_id: participantId })
  }

  async _handleClearDay() {
    if (!this._selectedDay) {
      return
    }
    await this._callService("clear_day", { day: this._selectedDay })
  }

  async _handleResetWeek() {
    await this._callService("reset_week", {})
  }

  async _callService(service, payload) {
    try {
      const data = { ...payload }
      if (this._config.entity) {
        data.entity_id = this._config.entity
      }
      await this._hass.callService(DAT_DOMAIN, service, data)
      this._setStatus("", false)
    } catch (error) {
      this._setStatus(`Fehler: ${error?.message || error}`, true)
    }
  }

  _trackerState() {
    if (!this._config.entity) {
      return null
    }
    return this._hass?.states?.[this._config.entity] || null
  }

  _attributes() {
    return this._trackerState()?.attributes || {}
  }

  _participants() {
    const participants = this._attributes().participants
    return Array.isArray(participants) ? participants : []
  }

  _days() {
    const days = this._attributes().days
    return days && typeof days === "object" ? days : {}
  }

  _todayKey() {
    const attrToday = this._attributes().today_key
    if (this._isDayKey(attrToday)) {
      return attrToday
    }

    const date = new Date()
    return DAT_DAYS[(date.getDay() + 6) % 7].key
  }

  _isDayKey(dayKey) {
    return DAT_DAYS.some((day) => day.key === dayKey)
  }

  _personOptions(participants) {
    const selectedEntities = new Set(
      participants
        .map((participant) => participant.entity_id)
        .filter(Boolean)
    )

    return Object.entries(this._hass?.states || {})
      .filter(([entityId]) => entityId.startsWith("person."))
      .filter(([entityId]) => !selectedEntities.has(entityId))
      .map(([entityId, state]) => ({
        entityId,
        name: state?.attributes?.friendly_name || entityId.replace(/^person\./, "").replace(/_/g, " ")
      }))
      .sort((left, right) => left.name.localeCompare(right.name))
  }

  _missingMessage() {
    if (this._multipleCandidates) {
      return '<div class="message">Mehrere Dinner Tracker gefunden. Bitte entity in der Card setzen.</div>'
    }
    if (this._config.entity) {
      return `<div class="message">Entity nicht gefunden: ${this._escapeHtml(this._config.entity)}</div>`
    }
    return '<div class="message">Bitte die Dinner Attendance Tracker Integration anlegen.</div>'
  }

  _setStatus(message, isError) {
    if (!this._status) {
      return
    }
    this._status.textContent = message || ""
    this._status.classList.toggle("error", Boolean(isError))

    window.clearTimeout(this._statusTimer)
    if (!message || !isError) {
      return
    }
    this._statusTimer = window.setTimeout(() => {
      this._status.textContent = ""
      this._status.classList.remove("error")
    }, 2500)
  }

  _escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
  }

  _escapeAttr(value) {
    return this._escapeHtml(value)
  }
}

if (!customElements.get("dinner-attendance-card")) {
  customElements.define("dinner-attendance-card", DinnerAttendanceCard)
}

window.customCards = window.customCards || []

if (!window.customCards.some((card) => card.type === "dinner-attendance-card")) {
  window.customCards.push({
    type: "dinner-attendance-card",
    name: "Dinner Attendance Card",
    description: `Weekly dinner and overnight attendance card (${DAT_CARD_VERSION})`
  })
}
