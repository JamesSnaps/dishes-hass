# Dishes — Home Assistant Integration & Card

A Home Assistant custom integration and Lovelace card for the [Dishes](https://github.com/JamesSnaps/dishes-app) self-hosted meal planning app.

- **Integration** — exposes your weekly meal plan as persistent sensors, usable in automations, dashboards, and voice assistants
- **Card** — displays the full week's meal grid on any dashboard, with a visual editor

---

## Sensors

| Entity | State | Key Attributes |
|--------|-------|----------------|
| `sensor.dishes_next_meal` | Recipe name of the next upcoming meal | `meal_type`, `day_of_week`, `cuisine`, `prep_time_minutes`, `cook_time_minutes` |
| `sensor.dishes_tonight_dinner` | Tonight's dinner recipe name | `cuisine`, `prep_time_minutes`, `cook_time_minutes`, `servings` |
| `sensor.dishes_today_lunch` | Today's lunch recipe name | same as above |
| `sensor.dishes_today_breakfast` | Today's breakfast recipe name | same as above |
| `sensor.dishes_week_plan_status` | `active` / `draft` / `none` | `week_start`, `meal_count` |

Sensors show `None` when no meal is planned for that slot.

---

## Installation

### Integration (via HACS — recommended)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/JamesSnaps/dishes-hass` with category **Integration**
3. Search for "Dishes" and install
4. Restart Home Assistant

### Integration (manual)

Copy `custom_components/dishes/` into your HA `config/custom_components/` folder and restart.

### Card (manual)

Copy `www/dishes-week-card.js` into your HA `config/www/` folder, then register it as a Lovelace resource:

```yaml
lovelace:
  resources:
    - url: /local/dishes-week-card.js
      type: module
```

Then add a card to your dashboard — search for **Dishes Week Planner** in the card picker and fill in the URL and token via the visual editor.

---

## Integration Setup

1. In HA go to **Settings → Devices & Services → Add Integration** and search for **Dishes**
2. Enter your Dishes app URL (e.g. `https://dishes.home.example.com`)
3. Enter an integration token — create one in Dishes under **Settings → Integrations** with the `read:meal_plan` scope

---

## Example Automations

**Notify at 5pm with tonight's dinner:**
```yaml
automation:
  trigger:
    platform: time
    at: "17:00:00"
  condition:
    condition: not
    conditions:
      - condition: state
        entity_id: sensor.dishes_tonight_dinner
        state: "None"
  action:
    service: notify.mobile_app
    data:
      message: "Tonight's dinner: {{ states('sensor.dishes_tonight_dinner') }}"
```

**Announce next meal on a speaker:**
```yaml
action:
  service: tts.speak
  data:
    message: >
      The next meal is {{ states('sensor.dishes_next_meal') }},
      a {{ state_attr('sensor.dishes_next_meal', 'meal_type') }}
      on {{ state_attr('sensor.dishes_next_meal', 'day_of_week') }}.
```

---

## Requirements

- Dishes app v1.x or later with integrations API enabled
- Home Assistant 2023.1.0 or later
