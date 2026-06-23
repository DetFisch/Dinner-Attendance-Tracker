const DAT_DOMAIN = "dinner_attendance_tracker"
const DAT_CARD_VERSION = "0.2.1"
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
    const configuredMe = config.me_entity || config.me || config.person_entity || null
    this._config = {
      name: config.name || DAT_DEFAULT_TITLE,
      entity: config.entity || null,
      me_entity: configuredMe || this._storedMeEntity(config.entity || "auto"),
      me_entity_configured: Boolean(configuredMe),
      default_dinner: this._entityList(config.default_dinner || config.default_dinner_entities),
      default_overnight: this._entityList(config.default_overnight || config.default_overnight_entities),
      defaults: Array.isArray(config.defaults) ? config.defaults : []
    }
    this._selectedDay = this._isDayKey(config.default_day)
      ? config.default_day
      : this._isDayKey(this._selectedDay)
        ? this._selectedDay
        : null
  }

  set hass(hass) {
    this._hass = hass

    if (!this._root) {
      this._renderSkeleton()
      this._attachEvents()
    }

    this._syncEntity()
    this._renderState()
    this._syncConfiguredPeople()
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

        ha-dialog {
          --dialog-content-padding: 0 24px 20px;
          --mdc-dialog-min-width: min(520px, calc(100vw - 32px));
          --mdc-dialog-max-width: min(560px, calc(100vw - 32px));
        }

        .dialog-content {
          display: grid;
          gap: 14px;
          padding-top: 8px;
        }

        .dialog-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }

        .dialog-title {
          min-width: 0;
          font-size: 1.05rem;
          font-weight: 600;
          color: var(--primary-text-color);
        }

        .dialog-section {
          display: grid;
          gap: 8px;
        }

        .section-title {
          color: var(--secondary-text-color);
          font-size: 0.78rem;
          font-weight: 600;
          text-transform: uppercase;
        }

        .section-title-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }

        .small-text-button {
          min-height: 28px;
          padding: 0 8px;
          color: var(--secondary-text-color);
          font-size: 0.78rem;
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

        .participant-row.me {
          border-color: var(--primary-color);
          background: color-mix(in srgb, var(--primary-color) 8%, transparent);
        }

        .participant-name-wrap {
          display: grid;
          gap: 2px;
          min-width: 0;
          padding-left: 4px;
        }

        .participant-name {
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: var(--primary-text-color);
        }

        .participant-meta {
          display: flex;
          align-items: center;
          gap: 4px;
          min-width: 0;
          color: var(--secondary-text-color);
          font-size: 0.75rem;
          flex-wrap: wrap;
        }

        .mini-badge {
          display: inline-flex;
          align-items: center;
          max-width: 100%;
          padding: 1px 6px;
          border-radius: var(--ha-border-radius-pill, 999px);
          background: var(--secondary-background-color);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .toggle-group {
          display: inline-flex;
          gap: 4px;
          align-items: center;
        }

        .default-group {
          display: flex;
          gap: 4px;
          flex-wrap: wrap;
          padding-top: 2px;
        }

        .default-toggle {
          min-height: 24px;
          padding: 0 7px;
          font-size: 0.74rem;
          color: var(--secondary-text-color);
        }

        .default-toggle[aria-pressed="true"] {
          border-color: var(--primary-color);
          color: var(--primary-text-color);
          background: color-mix(in srgb, var(--primary-color) 18%, transparent);
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

        .toggle ha-icon,
        .remove-button ha-icon {
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

        .remove-button,
        .icon-button {
          width: 32px;
          height: 32px;
          padding: 0;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          color: var(--secondary-text-color);
        }

        .add-grid {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 8px;
          align-items: end;
        }

        .add-options {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          align-items: center;
          grid-column: 1 / -1;
        }

        .check-option {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          min-height: 28px;
          color: var(--secondary-text-color);
          font-size: 0.82rem;
        }

        .check-option input {
          width: auto;
          min-height: auto;
          margin: 0;
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
          </div>
          <div id="content"></div>
          <div id="status" class="status"></div>
        </div>
      </ha-card>
      <ha-dialog id="day-dialog"></ha-dialog>
    `

    this._root = this.querySelector("ha-card")
    this._content = this.querySelector("#content")
    this._status = this.querySelector("#status")
    this._dialog = this.querySelector("#day-dialog")
  }

  _attachEvents() {
    this.addEventListener("click", (event) => {
      const target = event.target
      if (!(target instanceof Element)) {
        return
      }

      const dayRow = target.closest("[data-day-row]")
      if (dayRow) {
        this._selectedDay = dayRow.getAttribute("data-day-row")
        this._openDialog()
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

      const setMe = target.closest("[data-set-me]")
      if (setMe) {
        this._handleSetMe()
        return
      }

      const clearMe = target.closest("[data-clear-me]")
      if (clearMe) {
        this._handleClearMe()
        return
      }

      const defaultToggle = target.closest("[data-default-action]")
      if (defaultToggle) {
        this._handleDefaultToggle(defaultToggle)
        return
      }

      const addGuest = target.closest("[data-add-guest]")
      if (addGuest) {
        this._handleAddGuest()
        return
      }

      const closeDialog = target.closest("[data-close-dialog]")
      if (closeDialog) {
        this._dialog.open = false
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
      this._syncStoredMeEntity()
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
    this._syncStoredMeEntity()
  }

  _syncStoredMeEntity() {
    if (this._config.me_entity || this._config.me_entity_configured) {
      return
    }
    const stored = this._storedMeEntity(this._config.entity || "auto") || this._storedMeEntity("auto")
    if (stored) {
      this._config.me_entity = stored
    }
  }

  _renderState() {
    this.querySelector("#title").textContent = this._config.name || DAT_DEFAULT_TITLE

    const state = this._trackerState()
    if (!state) {
      this._content.innerHTML = this._missingMessage()
      if (this._dialog) {
        this._dialog.open = false
      }
      return
    }

    if (!this._selectedDay) {
      this._selectedDay = this._todayKey()
    }

    this._content.innerHTML = this._renderWeek()
    if (this._dialog?.open) {
      this._renderDialog()
    }
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
    const selected = this._selectedDay === day.key && this._dialog?.open ? " selected" : ""

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

  _openDialog() {
    this._renderDialog()
    this._dialog.open = true
    this._renderState()
  }

  _renderDialog() {
    if (!this._dialog || !this._selectedDay) {
      return
    }

    const day = DAT_DAYS.find((item) => item.key === this._selectedDay) || DAT_DAYS[0]
    const dayState = this._days()[day.key] || { dinner: [], overnight: [] }
    const participants = this._participants()
    const meEntity = this._config.me_entity
    const otherParticipants = participants.filter((participant) => participant.id !== meEntity)
    const personOptions = this._personOptions(participants)

    this._dialog.innerHTML = `
      <div class="dialog-content">
        <div class="dialog-head">
          <div class="dialog-title">${day.name}</div>
          <button class="icon-button" data-close-dialog title="Schließen" aria-label="Schließen" type="button">
            <ha-icon icon="mdi:close"></ha-icon>
          </button>
        </div>

        ${this._renderMeSection(dayState)}

        <section class="dialog-section">
          <div class="section-title">Andere Personen und Gäste</div>
          <div class="participant-list">
            ${otherParticipants.length ? otherParticipants.map((participant) => (
              this._renderParticipantRow(participant, dayState, { removable: true })
            )).join("") : '<div class="message">Keine weiteren Personen oder Gäste.</div>'}
          </div>
        </section>

        <section class="dialog-section">
          <div class="section-title">Hinzufügen</div>
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
            <div class="add-options">
              <label class="check-option">
                <input id="person-default-dinner" type="checkbox">
                Standard Essen
              </label>
              <label class="check-option">
                <input id="person-default-overnight" type="checkbox">
                Standard Nacht
              </label>
            </div>
          </div>

          <div class="add-grid">
            <label class="field">
              <span>Gast</span>
              <input id="guest-name" type="text" autocomplete="off" placeholder="Name">
            </label>
            <button class="text-button" data-add-guest type="button">Hinzufügen</button>
          </div>
        </section>

        <div class="dialog-head">
          <button class="text-button" data-clear-day type="button">Tag auf Standard</button>
          <button class="text-button danger" data-reset-week type="button">Woche auf Standard</button>
        </div>
      </div>
    `
  }

  _renderMeSection(dayState) {
    const meEntity = this._config.me_entity
    if (!meEntity) {
      const options = this._allPersonOptions()
      return `
        <section class="dialog-section">
          <div class="section-title">Ich</div>
          <div class="add-grid">
            <label class="field">
              <span>Person für dieses Dashboard</span>
              <select id="me-select">
                ${options.length
                  ? '<option value="">Ich wählen...</option>' + options.map((person) => (
                    `<option value="${this._escapeAttr(person.entityId)}">${this._escapeHtml(person.name)}</option>`
                  )).join("")
                  : '<option value="">Keine Home Assistant Personen gefunden</option>'}
              </select>
            </label>
            <button class="text-button" data-set-me type="button" ${options.length ? "" : "disabled"}>Festlegen</button>
          </div>
        </section>
      `
    }

    const meParticipant = this._participantById(meEntity) || {
      id: meEntity,
      type: "person",
      name: this._friendlyPersonName(meEntity),
      entity_id: meEntity,
      default_dinner: this._configuredDefaults().get(meEntity)?.dinner || false,
      default_overnight: this._configuredDefaults().get(meEntity)?.overnight || false
    }

    return `
      <section class="dialog-section">
        <div class="section-title-row">
          <div class="section-title">Ich</div>
          ${this._config.me_entity_configured ? "" : '<button class="small-text-button" data-clear-me type="button">Ändern</button>'}
        </div>
        <div class="participant-list">
          ${this._renderParticipantRow(meParticipant, dayState, {
            removable: false,
            me: true,
            ensurePerson: meEntity
          })}
        </div>
      </section>
    `
  }

  _renderParticipantRow(participant, dayState, options = {}) {
    const participantId = String(participant.id)
    const dinner = Array.isArray(dayState.dinner) && dayState.dinner.includes(participantId)
    const overnight = Array.isArray(dayState.overnight) && dayState.overnight.includes(participantId)
    const escapedId = this._escapeAttr(participantId)
    const escapedName = this._escapeHtml(participant.name)
    const ensureAttr = options.ensurePerson ? ` data-person-entity-id="${this._escapeAttr(options.ensurePerson)}"` : ""
    const meta = this._participantMeta(participant)

    return `
      <div class="participant-row${options.me ? " me" : ""}">
        <div class="participant-name-wrap">
          <div class="participant-name" title="${this._escapeAttr(participant.name)}">${escapedName}</div>
          ${meta ? `<div class="participant-meta">${meta}</div>` : ""}
          ${this._renderDefaultControls(participant)}
        </div>
        <div class="toggle-group">
          <button
            class="toggle"
            data-attendance-action="dinner"
            data-participant-id="${escapedId}"
            ${ensureAttr}
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
            ${ensureAttr}
            aria-pressed="${overnight ? "true" : "false"}"
            title="Übernachtung"
            type="button"
          >
            <ha-icon icon="mdi:bed"></ha-icon>
            Nacht
          </button>
        </div>
        ${options.removable ? `
          <button
            class="remove-button"
            data-remove-participant="${escapedId}"
            title="Entfernen"
            aria-label="Entfernen"
            type="button"
          >
            <ha-icon icon="mdi:close"></ha-icon>
          </button>
        ` : '<span></span>'}
      </div>
    `
  }

  _participantMeta(participant) {
    const badges = []
    if (participant.default_dinner) {
      badges.push('<span class="mini-badge">Standard Essen</span>')
    }
    if (participant.default_overnight) {
      badges.push('<span class="mini-badge">Standard Nacht</span>')
    }
    return badges.join("")
  }

  _renderDefaultControls(participant) {
    if (participant.type !== "person") {
      return ""
    }
    const ensureAttr = participant.entity_id
      ? ` data-person-entity-id="${this._escapeAttr(participant.entity_id)}"`
      : ""

    return `
      <div class="default-group">
        <button
          class="default-toggle"
          data-default-action="dinner"
          data-participant-id="${this._escapeAttr(participant.id)}"
          ${ensureAttr}
          aria-pressed="${participant.default_dinner ? "true" : "false"}"
          type="button"
        >Immer Essen</button>
        <button
          class="default-toggle"
          data-default-action="overnight"
          data-participant-id="${this._escapeAttr(participant.id)}"
          ${ensureAttr}
          aria-pressed="${participant.default_overnight ? "true" : "false"}"
          type="button"
        >Immer Nacht</button>
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
    const personEntityId = toggle.getAttribute("data-person-entity-id")
    if (!participantId || !action || !this._selectedDay) {
      return
    }

    const enabled = toggle.getAttribute("aria-pressed") !== "true"
    if (personEntityId && !this._participantById(participantId)) {
      await this._callService("add_person", { person_entity_id: personEntityId })
      await this._applyConfiguredDefault(personEntityId)
    }

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
    const defaultDinner = Boolean(this.querySelector("#person-default-dinner")?.checked)
    const defaultOvernight = Boolean(this.querySelector("#person-default-overnight")?.checked)
    if (defaultDinner || defaultOvernight) {
      await this._callService("set_person_defaults", {
        participant_id: personEntityId,
        default_dinner: defaultDinner,
        default_overnight: defaultOvernight
      })
    } else {
      await this._applyConfiguredDefault(personEntityId)
    }
    if (select) {
      select.value = ""
    }
    const dinnerCheckbox = this.querySelector("#person-default-dinner")
    const overnightCheckbox = this.querySelector("#person-default-overnight")
    if (dinnerCheckbox) {
      dinnerCheckbox.checked = false
    }
    if (overnightCheckbox) {
      overnightCheckbox.checked = false
    }
  }

  async _handleSetMe() {
    const select = this.querySelector("#me-select")
    const personEntityId = String(select?.value || "").trim()
    if (!personEntityId) {
      this._setStatus("Bitte eine Person für Ich auswählen.", true)
      return
    }

    this._config.me_entity = personEntityId
    this._storeMeEntity(personEntityId)
    if (!this._participantById(personEntityId)) {
      await this._callService("add_person", { person_entity_id: personEntityId })
    }
    await this._applyConfiguredDefault(personEntityId)
    this._renderState()
  }

  _handleClearMe() {
    if (this._config.me_entity_configured) {
      return
    }
    this._config.me_entity = null
    this._clearStoredMeEntity()
    this._renderState()
  }

  async _handleDefaultToggle(toggle) {
    const participantId = toggle.getAttribute("data-participant-id")
    const action = toggle.getAttribute("data-default-action")
    const personEntityId = toggle.getAttribute("data-person-entity-id")
    let participant = this._participantById(participantId)
    if (!participant && personEntityId) {
      await this._callService("add_person", { person_entity_id: personEntityId })
      participant = {
        id: personEntityId,
        type: "person",
        default_dinner: false,
        default_overnight: false
      }
    }
    if (!participant || participant.type !== "person" || !action) {
      return
    }

    const nextValue = toggle.getAttribute("aria-pressed") !== "true"
    await this._callService("set_person_defaults", {
      participant_id: participantId,
      default_dinner: action === "dinner" ? nextValue : Boolean(participant.default_dinner),
      default_overnight: action === "overnight" ? nextValue : Boolean(participant.default_overnight)
    })
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

  async _syncConfiguredPeople() {
    if (this._syncRunning || !this._hass || !this._trackerState()) {
      return
    }

    const people = new Set([...this._configuredDefaults().keys()])
    if (this._config.me_entity) {
      people.add(this._config.me_entity)
    }
    if (!people.size) {
      return
    }

    this._syncRunning = true
    try {
      for (const personEntityId of people) {
        if (!this._participantById(personEntityId)) {
          await this._callService("add_person", { person_entity_id: personEntityId }, { silent: true })
        }
        await this._applyConfiguredDefault(personEntityId, { silent: true })
      }
    } finally {
      this._syncRunning = false
    }
  }

  async _applyConfiguredDefault(personEntityId, options = {}) {
    const configured = this._configuredDefaults().get(personEntityId)
    if (!configured) {
      return
    }

    const participant = this._participantById(personEntityId)
    if (
      participant &&
      Boolean(participant.default_dinner) === Boolean(configured.dinner) &&
      Boolean(participant.default_overnight) === Boolean(configured.overnight)
    ) {
      return
    }

    await this._callService("set_person_defaults", {
      participant_id: personEntityId,
      default_dinner: Boolean(configured.dinner),
      default_overnight: Boolean(configured.overnight)
    }, options)
  }

  async _callService(service, payload, options = {}) {
    try {
      const data = { ...payload }
      if (this._config.entity) {
        data.entity_id = this._config.entity
      }
      await this._hass.callService(DAT_DOMAIN, service, data)
      if (!options.silent) {
        this._setStatus("", false)
      }
    } catch (error) {
      if (!options.silent) {
        this._setStatus(`Fehler: ${error?.message || error}`, true)
      }
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

  _participantById(participantId) {
    return this._participants().find((participant) => participant.id === participantId) || null
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
    if (this._config.me_entity) {
      selectedEntities.add(this._config.me_entity)
    }

    return Object.entries(this._hass?.states || {})
      .filter(([entityId]) => entityId.startsWith("person."))
      .filter(([entityId]) => !selectedEntities.has(entityId))
      .map(([entityId, state]) => ({
        entityId,
        name: state?.attributes?.friendly_name || entityId.replace(/^person\./, "").replace(/_/g, " ")
      }))
      .sort((left, right) => left.name.localeCompare(right.name))
  }

  _allPersonOptions() {
    return Object.entries(this._hass?.states || {})
      .filter(([entityId]) => entityId.startsWith("person."))
      .map(([entityId, state]) => ({
        entityId,
        name: state?.attributes?.friendly_name || entityId.replace(/^person\./, "").replace(/_/g, " ")
      }))
      .sort((left, right) => left.name.localeCompare(right.name))
  }

  _configuredDefaults() {
    const defaults = new Map()
    for (const entityId of this._config.default_dinner) {
      defaults.set(entityId, { ...(defaults.get(entityId) || {}), dinner: true })
    }
    for (const entityId of this._config.default_overnight) {
      defaults.set(entityId, { ...(defaults.get(entityId) || {}), overnight: true })
    }
    for (const entry of this._config.defaults) {
      const entityId = entry?.person || entry?.entity || entry?.entity_id
      if (!entityId) {
        continue
      }
      defaults.set(entityId, {
        ...(defaults.get(entityId) || {}),
        dinner: Boolean(entry.dinner),
        overnight: Boolean(entry.overnight)
      })
    }

    for (const [entityId, value] of defaults.entries()) {
      defaults.set(entityId, {
        dinner: Boolean(value.dinner),
        overnight: Boolean(value.overnight)
      })
    }
    return defaults
  }

  _entityList(value) {
    if (!value) {
      return []
    }
    const raw = Array.isArray(value) ? value : [value]
    return raw
      .map((item) => String(item || "").trim())
      .filter((item) => item.startsWith("person."))
  }

  _friendlyPersonName(entityId) {
    const state = this._hass?.states?.[entityId]
    return state?.attributes?.friendly_name || entityId.replace(/^person\./, "").replace(/_/g, " ")
  }

  _storageKey(suffix) {
    const entity = this._config?.entity || "auto"
    const path = window.location?.pathname || "dashboard"
    return `${DAT_DOMAIN}:${entity}:${path}:${suffix}`
  }

  _storedMeEntity(entity) {
    try {
      const path = window.location?.pathname || "dashboard"
      return window.localStorage?.getItem(`${DAT_DOMAIN}:${entity}:${path}:me`) || null
    } catch (_error) {
      return null
    }
  }

  _storeMeEntity(entityId) {
    if (this._config.me_entity_configured) {
      return
    }
    try {
      window.localStorage?.setItem(this._storageKey("me"), entityId)
    } catch (_error) {
      // localStorage may be unavailable in restricted browser contexts.
    }
  }

  _clearStoredMeEntity() {
    if (this._config.me_entity_configured) {
      return
    }
    try {
      const path = window.location?.pathname || "dashboard"
      const entities = new Set([this._config?.entity || "auto", "auto"])
      for (const entity of entities) {
        window.localStorage?.removeItem(`${DAT_DOMAIN}:${entity}:${path}:me`)
      }
    } catch (_error) {
      // localStorage may be unavailable in restricted browser contexts.
    }
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
