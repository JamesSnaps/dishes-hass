// Dishes Week Planner — Home Assistant Lovelace custom card
// Copy this file to your HA config/www/ folder and register it as a resource.
//
// The card reads the week from the Dishes integration's "Week plan status"
// sensor, so it needs no URL or token of its own: the token stays on the Home
// Assistant server instead of in every browser that opens the dashboard.
//
// Card config:
//   type: custom:dishes-week-card
//   entity: sensor.dishes_week_plan_status   # optional, found automatically
//   title: This Week's Meals                 # optional
//   meal_types: [breakfast, lunch, dinner]   # optional, defaults shown
//   show_times: true                         # optional, serve times next to meals

const MEAL_TYPE_LABELS = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
  dessert: "Dessert",
  snack: "Snack",
};

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DEFAULT_MEAL_TYPES = ["breakfast", "lunch", "dinner"];
const ALL_MEAL_TYPES = ["breakfast", "lunch", "snack", "dinner", "dessert"];

// Recipe titles and notes come from Dishes: never put them into HTML unescaped.
const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** Sensors the Dishes integration publishes the week on. */
const weekSensors = (hass) =>
  Object.keys(hass?.states ?? {}).filter(
    (id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes.meals) && "dishes_url" in hass.states[id].attributes
  );

// ---------------------------------------------------------------------------
// Card editor — shown in the visual dashboard editor
// ---------------------------------------------------------------------------

class DishesWeekCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._render();
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }

  _render() {
    const cfg = this._config;
    const selectedTypes = cfg.meal_types || DEFAULT_MEAL_TYPES;
    const sensors = weekSensors(this._hass);

    this.shadowRoot.innerHTML = `
      <style>
        .form { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
        label { font-size: 0.85rem; color: var(--secondary-text-color, #727272); display: block; margin-bottom: 3px; }
        input[type="text"], select {
          width: 100%;
          box-sizing: border-box;
          padding: 8px 10px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 6px;
          font-size: 0.9rem;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #212121);
        }
        .checkboxes { display: flex; flex-wrap: wrap; gap: 8px; }
        .checkbox-row { display: flex; align-items: center; gap: 5px; font-size: 0.85rem; cursor: pointer; }
        .checkbox-row input { cursor: pointer; }
        .hint { font-size: 0.8rem; color: var(--warning-color, #ff9800); }
      </style>
      <div class="form">
        <div>
          <label>Dishes week sensor</label>
          <select id="entity">
            <option value="">Automatic${sensors[0] ? ` (${escapeHtml(sensors[0])})` : ""}</option>
            ${sensors
              .map((id) => `<option value="${escapeHtml(id)}" ${cfg.entity === id ? "selected" : ""}>${escapeHtml(id)}</option>`)
              .join("")}
          </select>
          ${sensors.length ? "" : `<div class="hint">Set up the Dishes integration first — the card reads the week from it.</div>`}
        </div>
        <div>
          <label>Card title</label>
          <input id="title" type="text" placeholder="This Week's Meals" value="${escapeHtml(cfg.title || "")}">
        </div>
        <div>
          <label>Meal rows to show</label>
          <div class="checkboxes">
            ${ALL_MEAL_TYPES.map((t) => `
              <label class="checkbox-row">
                <input type="checkbox" data-type="${t}" ${selectedTypes.includes(t) ? "checked" : ""}>
                ${MEAL_TYPE_LABELS[t]}
              </label>`).join("")}
          </div>
        </div>
        <label class="checkbox-row">
          <input id="show_times" type="checkbox" ${cfg.show_times !== false ? "checked" : ""}>
          Show serve times
        </label>
      </div>`;

    // A card saved by 1.x drops its URL and token on the next edit.
    const { url: _url, token: _token, ...base } = this._config;

    this.shadowRoot.querySelector("#entity").addEventListener("change", (e) => {
      this._fire({ ...base, entity: e.target.value || undefined });
    });
    this.shadowRoot.querySelector("#title").addEventListener("change", (e) => {
      this._fire({ ...base, title: e.target.value.trim() || undefined });
    });
    this.shadowRoot.querySelector("#show_times").addEventListener("change", (e) => {
      this._fire({ ...base, show_times: e.target.checked ? undefined : false });
    });
    this.shadowRoot.querySelectorAll("input[data-type]").forEach((cb) => {
      cb.addEventListener("change", () => {
        const checked = [...this.shadowRoot.querySelectorAll("input[data-type]:checked")].map((el) => el.dataset.type);
        this._fire({ ...base, meal_types: checked.length ? checked : DEFAULT_MEAL_TYPES });
      });
    });
  }
}

customElements.define("dishes-week-card-editor", DishesWeekCardEditor);

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

class DishesWeekCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._stateObj = undefined;
  }

  static getStubConfig() {
    return { title: "This Week's Meals", meal_types: DEFAULT_MEAL_TYPES };
  }

  static getConfigElement() {
    return document.createElement("dishes-week-card-editor");
  }

  setConfig(config) {
    this._config = {
      entity: config.entity,
      title: config.title || "This Week's Meals",
      meal_types: config.meal_types || DEFAULT_MEAL_TYPES,
      show_times: config.show_times !== false,
      // 1.x cards fetched Dishes with a token kept in the dashboard config.
      legacyToken: Boolean(config.token),
    };
    this._stateObj = undefined;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const entity = this._config?.entity || weekSensors(hass)[0];
    // null, never undefined, when missing: undefined means "not drawn yet".
    const stateObj = (entity && hass.states[entity]) || null;
    // Only redraw when the week sensor itself changed, not on every HA update.
    if (stateObj !== this._stateObj) {
      this._entity = entity;
      this._stateObj = stateObj;
      this._render();
    }
  }

  _buildStack(attrs) {
    const { meal_types: mealTypes, show_times: showTimes } = this._config;
    const byDay = DAY_LABELS.map(() => []);
    for (const meal of attrs.meals) {
      if (mealTypes.includes(meal.meal_type)) byDay[meal.day_of_week]?.push(meal);
    }
    const order = (m) => mealTypes.indexOf(m.meal_type);
    const todayIndex = attrs.today ? (new Date(`${attrs.today}T12:00:00`).getDay() + 6) % 7 : -1;

    const dayRows = byDay
      .map((meals, dayIndex) => {
        if (meals.length === 0) return "";
        const items = meals
          .sort((a, b) => order(a) - order(b))
          .map((m) => {
            const time =
              showTimes && m.serve_at
                ? `<span class="meal-time">${escapeHtml(m.serve_at.slice(11, 16))}</span>`
                : "";
            const dishes = m.dishes.length > 1 ? m.dishes.join(", ") : "";
            const tip = [dishes, m.notes].filter(Boolean).join(" — ");
            return `
              <div class="meal-row">
                <span class="meal-type">${escapeHtml(MEAL_TYPE_LABELS[m.meal_type] || m.meal_type)}</span>
                <a class="meal-name" href="${escapeHtml(m.url)}" target="_blank" rel="noreferrer" title="${escapeHtml(tip)}">${escapeHtml(m.title)}</a>
                ${time}
              </div>`;
          })
          .join("");
        return `
          <div class="day-block${dayIndex === todayIndex ? " today" : ""}">
            <div class="day-name">${DAY_LABELS[dayIndex]}</div>
            <div class="meal-list">${items}</div>
          </div>`;
      })
      .filter(Boolean);

    return dayRows.length
      ? `<div class="stack">${dayRows.join("")}</div>`
      : `<div class="state">No meals planned this week.</div>`;
  }

  _render() {
    if (!this._config) return;
    const title = escapeHtml(this._config.title);
    const stateObj = this._stateObj;
    let body;

    if (!this._hass) {
      body = `<div class="state">Loading…</div>`;
    } else if (!stateObj) {
      body = `<div class="state error">${
        this._entity
          ? `${escapeHtml(this._entity)} not found.`
          : "No Dishes week sensor found — set up the Dishes integration."
      }</div>`;
    } else if (!Array.isArray(stateObj.attributes.meals)) {
      body = `<div class="state">No meals yet.</div>`;
    } else {
      body = this._buildStack(stateObj.attributes);
    }

    const legacy = this._config.legacyToken
      ? `<div class="hint">This card no longer uses a token — remove <code>url</code> and <code>token</code> from its config (and revoke the token in Dishes if nothing else uses it).</div>`
      : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; font-family: var(--primary-font-family, sans-serif); }
        .card { padding: 16px; overflow: hidden; }
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
        .title { font-size: 1rem; font-weight: 600; color: var(--primary-text-color, #212121); }
        .stack { display: flex; flex-direction: column; }
        .day-block {
          display: flex; align-items: baseline; gap: 12px;
          padding: 8px 0;
          border-top: 1px solid var(--divider-color, #e8e8e8);
        }
        .day-block:first-child { border-top: none; }
        .day-name { flex: 0 0 36px; font-weight: 600; font-size: 0.8rem; color: var(--secondary-text-color, #727272); }
        .day-block.today .day-name { color: var(--primary-color, #03a9f4); }
        .meal-list { flex: 1; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
        .meal-row { display: flex; align-items: baseline; gap: 8px; }
        .meal-type {
          flex: 0 0 76px;
          font-size: 0.72rem; font-weight: 500;
          color: var(--secondary-text-color, #727272);
          text-transform: uppercase; letter-spacing: 0.02em;
        }
        .meal-name {
          flex: 1; min-width: 0;
          font-size: 0.88rem; line-height: 1.3;
          color: var(--primary-text-color, #212121);
          text-decoration: none;
        }
        .meal-name:hover { color: var(--primary-color, #03a9f4); text-decoration: underline; }
        .meal-time { font-size: 0.75rem; color: var(--secondary-text-color, #727272); font-variant-numeric: tabular-nums; }
        .state { text-align: center; color: var(--secondary-text-color, #727272); padding: 16px 0; font-size: 0.9rem; }
        .state.error { color: var(--error-color, #db4437); font-size: 0.8rem; }
        .hint { margin-top: 10px; font-size: 0.75rem; color: var(--warning-color, #ff9800); }
      </style>
      <ha-card>
        <div class="card">
          <div class="header"><span class="title">${title}</span></div>
          ${body}
          ${legacy}
        </div>
      </ha-card>`;
  }

  getCardSize() {
    return 3;
  }
}

customElements.define("dishes-week-card", DishesWeekCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "dishes-week-card",
  name: "Dishes Week Planner",
  description: "This week's meals from the Dishes integration.",
});
