// Dishes Week Planner — Home Assistant Lovelace custom card
// Copy this file to your HA config/www/ folder and register it as a resource.
//
// Card config:
//   type: custom:dishes-week-card
//   url: https://your-dishes-app.example.com
//   token: your_integration_token_here
//   title: This Week's Meals          # optional
//   meal_types: [breakfast, lunch, dinner]  # optional, defaults shown

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

// ---------------------------------------------------------------------------
// Card editor — shown in the visual dashboard editor
// ---------------------------------------------------------------------------

class DishesWeekCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
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

    this.shadowRoot.innerHTML = `
      <style>
        .form { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
        label { font-size: 0.85rem; color: var(--secondary-text-color, #727272); display: block; margin-bottom: 3px; }
        input[type="text"], input[type="url"] {
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
      </style>
      <div class="form">
        <div>
          <label>Dishes URL *</label>
          <input id="url" type="url" placeholder="https://dishes.home.example.com" value="${cfg.url || ""}">
        </div>
        <div>
          <label>Integration Token *</label>
          <input id="token" type="text" placeholder="your_integration_token" value="${cfg.token || ""}">
        </div>
        <div>
          <label>Card Title</label>
          <input id="title" type="text" placeholder="This Week's Meals" value="${cfg.title || ""}">
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
      </div>`;

    this.shadowRoot.querySelector("#url").addEventListener("change", (e) => {
      this._fire({ ...this._config, url: e.target.value.trim().replace(/\/$/, "") });
    });
    this.shadowRoot.querySelector("#token").addEventListener("change", (e) => {
      this._fire({ ...this._config, token: e.target.value.trim() });
    });
    this.shadowRoot.querySelector("#title").addEventListener("change", (e) => {
      this._fire({ ...this._config, title: e.target.value.trim() || undefined });
    });
    this.shadowRoot.querySelectorAll("input[data-type]").forEach((cb) => {
      cb.addEventListener("change", () => {
        const checked = [...this.shadowRoot.querySelectorAll("input[data-type]:checked")]
          .map((el) => el.dataset.type);
        this._fire({ ...this._config, meal_types: checked.length ? checked : DEFAULT_MEAL_TYPES });
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
    this._data = null;
    this._error = null;
    this._loading = false;
  }

  static getStubConfig() {
    return {
      url: "",
      token: "",
      title: "This Week's Meals",
      meal_types: DEFAULT_MEAL_TYPES,
    };
  }

  static getConfigElement() {
    return document.createElement("dishes-week-card-editor");
  }

  setConfig(config) {
    if (!config.url) throw new Error("dishes-week-card: 'url' is required");
    if (!config.token) throw new Error("dishes-week-card: 'token' is required");
    this._config = {
      url: config.url.replace(/\/$/, ""),
      token: config.token,
      title: config.title || "This Week's Meals",
      meal_types: config.meal_types || DEFAULT_MEAL_TYPES,
    };
    this._fetchData();
  }

  connectedCallback() {
    if (this._config && !this._data && !this._loading) {
      this._fetchData();
    }
  }

  async _fetchData() {
    this._loading = true;
    this._error = null;
    this._render();

    try {
      const res = await fetch(
        `${this._config.url}/api/integrations/meal-plan/week`,
        { headers: { Authorization: `Bearer ${this._config.token}` } }
      );
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`${res.status}: ${body}`);
      }
      this._data = await res.json();
    } catch (e) {
      this._error = e.message;
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _buildGrid() {
    const { entries } = this._data;
    const mealTypes = this._config.meal_types;

    const index = {};
    for (const entry of entries) {
      const key = `${entry.dayOfWeek}:${entry.mealType}`;
      if (!index[key]) index[key] = [];
      index[key].push(entry);
    }

    const todayIndex = this._getTodayIndex();

    const rows = mealTypes.map((mealType) => {
      const cells = DAY_LABELS.map((_, dayIndex) => {
        const meals = index[`${dayIndex}:${mealType}`] || [];
        if (meals.length === 0) return `<td class="cell empty">—</td>`;
        const items = meals
          .map((m) => `<span class="recipe-name" title="${m.notes || ""}">${m.recipe.title}</span>`)
          .join("");
        return `<td class="cell">${items}</td>`;
      });
      return `
        <tr>
          <th class="meal-label">${MEAL_TYPE_LABELS[mealType] || mealType}</th>
          ${cells.join("")}
        </tr>`;
    });

    const dayHeaders = DAY_LABELS.map((label, i) =>
      `<th class="day-header${i === todayIndex ? " today" : ""}">${label}</th>`
    ).join("");

    return `
      <table class="grid">
        <thead><tr><th class="corner"></th>${dayHeaders}</tr></thead>
        <tbody>${rows.join("")}</tbody>
      </table>`;
  }

  _getTodayIndex() {
    const jsDay = new Date().getDay();
    return jsDay === 0 ? 6 : jsDay - 1;
  }

  _render() {
    const title = this._config?.title || "This Week's Meals";

    let body;
    if (this._loading) {
      body = `<div class="state">Loading…</div>`;
    } else if (this._error) {
      body = `<div class="state error">Failed to load meals: ${this._error}</div>`;
    } else if (!this._data) {
      body = `<div class="state">No data</div>`;
    } else if (this._data.entries.length === 0) {
      body = `<div class="state">No meals planned this week.</div>`;
    } else {
      body = this._buildGrid();
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; font-family: var(--primary-font-family, sans-serif); }
        .card {
          background: var(--card-background-color, #fff);
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,.15));
          padding: 16px;
          overflow: hidden;
        }
        .header {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 12px;
        }
        .title { font-size: 1rem; font-weight: 600; color: var(--primary-text-color, #212121); }
        .refresh-btn {
          background: none; border: none; cursor: pointer;
          color: var(--secondary-text-color, #727272);
          padding: 2px 4px; border-radius: 4px; font-size: 0.85rem; line-height: 1;
        }
        .refresh-btn:hover { color: var(--primary-color, #03a9f4); }
        .grid { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
        .corner { width: 60px; }
        .day-header {
          text-align: center; font-weight: 600;
          color: var(--secondary-text-color, #727272);
          padding: 4px 2px; width: calc((100% - 60px) / 7);
        }
        .day-header.today { color: var(--primary-color, #03a9f4); }
        .meal-label {
          text-align: left; font-weight: 500;
          color: var(--secondary-text-color, #727272);
          padding: 5px 4px 5px 0; white-space: nowrap;
          font-size: 0.72rem; vertical-align: top;
        }
        .cell {
          text-align: center; padding: 4px 3px; vertical-align: top;
          border-top: 1px solid var(--divider-color, #e8e8e8);
        }
        .cell.empty { color: var(--disabled-text-color, #bdbdbd); }
        .recipe-name {
          display: -webkit-box; color: var(--primary-text-color, #212121);
          line-height: 1.3; overflow: hidden;
          -webkit-line-clamp: 2; -webkit-box-orient: vertical;
        }
        .state {
          text-align: center; color: var(--secondary-text-color, #727272);
          padding: 16px 0; font-size: 0.9rem;
        }
        .state.error { color: var(--error-color, #db4437); font-size: 0.8rem; }
      </style>
      <ha-card>
        <div class="card">
          <div class="header">
            <span class="title">${title}</span>
            <button class="refresh-btn" title="Refresh">↺</button>
          </div>
          ${body}
        </div>
      </ha-card>`;

    this.shadowRoot
      .querySelector(".refresh-btn")
      ?.addEventListener("click", () => this._fetchData());
  }

  getCardSize() {
    return 3;
  }
}

customElements.define("dishes-week-card", DishesWeekCard);
