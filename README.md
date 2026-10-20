# Dishes — Home Assistant Integration & Card

A Home Assistant custom integration and Lovelace card for the [Dishes](https://github.com/JamesSnaps/dishes-app) self-hosted meal planning app.

- **Integration** — your meal plan, tonight's dinner times, who's cooking (with their step and timers), the shopping list and grocery deliveries, as entities for automations, dashboards and voice assistants
- **Card** — the week's meals on any dashboard, with a visual editor

---

## Entities

Entity ids below are the defaults. Which entities you get depends on the scopes of the token you give the integration (see [Setup](#integration-setup)).

### Meal plan — `read:meal_plan` (required)

| Entity | State | Key attributes |
|--------|-------|----------------|
| `sensor.dishes_next_meal` | The meal being eaten now, or the next one (into next week on a Sunday night) | `meal_type`, `day_of_week`, `date`, `serve_at`, `dishes`, `recipe_url`, `cook_url`, `cuisine`, `prep_time_minutes`, `cook_time_minutes` |
| `sensor.dishes_tonight_s_dinner` | Tonight's dinner | same, without the day |
| `sensor.dishes_today_s_lunch` | Today's lunch | same |
| `sensor.dishes_today_s_breakfast` | Today's breakfast | same |
| `sensor.dishes_week_plan_status` | `active` / `draft` / `archived` / `none` | `week_start`, `meal_count`, `meals` (the week, for the card) |
| `sensor.dishes_dinner_time` | When dinner is tonight (timestamp) | `time`, `reminder_enabled` |
| `sensor.dishes_start_cooking` | When to start cooking tonight's dinner to eat on time (timestamp) — what Dishes' own reminder goes by | `dinner` |
| `sensor.dishes_next_delivery` | Date of the next grocery delivery still to order | `status`, `slot`, `total`, `order_by`, `items_not_in_basket`, … |
| `sensor.dishes_order_deadline` | When that order closes (timestamp) | `delivery_date`, `ordered` |
| `calendar.dishes_meal_plan` | Every meal as a calendar event at its serve time | — |

A meal is everything planned for that slot: a combined meal shows by its name and a dish on its own by its title, so a roast with sides and a trifle reads **Sunday roast & Trifle**, with each dish in `dishes`. A meal with no slot is `unknown`.

Times are the household's (Dishes → Settings → Dinner reminders): dinner is at the household's dinner time for the day, or the meal's own ready-by time. Meals with no time in Dishes are assumed at breakfast 08:00, lunch 12:30, snack 15:30, dinner 18:00, dessert 19:30; their `serve_at` attribute is then empty. "Today" turns over at the household's midnight.

### Who's cooking — `read:cooking`

| Entity | State | Key attributes |
|--------|-------|----------------|
| `binary_sensor.dishes_cooking` | On while anyone is in cooking mode, on any device | `cooks`, `meals` |
| `binary_sensor.dishes_<name>_cooking` | One per household member, e.g. `binary_sensor.dishes_james_cooking` | `meal`, `dish`, `step`, `total_steps`, `device` |
| `sensor.dishes_cook` | Who's cooking (`James`, `James & Sam`), or `Nobody` | `cooks` |
| `sensor.dishes_cooking_step` | The step on screen in cooking mode | `step`, `total_steps`, `progress`, `dish`, `member`, `instruction` |
| `sensor.dishes_next_timer` | When the next cooking-mode timer goes off (timestamp) | `label`, `dish`, `member`, `running_timers`, `timers` |

Checked every 30 seconds (adjustable). The timer sensor holds the timer's end time, so a time trigger on it fires on the second, whenever the last check was. A cooking mode left open but untouched for 15 minutes, with no timer running, stops counting as cooking.

### Shopping list — `read:shopping_list` (+ `write:shopping_list`)

| Entity | State |
|--------|-------|
| `todo.dishes_shopping_list` | Items still to buy |

With `write:shopping_list` it's two-way: add items (including by voice — "add milk to the shopping list" with Assist), tick them off, rename and remove them. With only `read:shopping_list` it's read-only.

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

Copy `www/dishes-week-card.js` into your HA `config/www/` folder, then register it as a Lovelace resource (**Settings → Dashboards → ⋮ → Resources**, or in YAML):

```yaml
lovelace:
  resources:
    - url: /local/dishes-week-card.js
      type: module
```

Then add a card to your dashboard — search for **Dishes Week Planner** in the card picker. It reads the week from the integration's `sensor.dishes_week_plan_status`, so set up the integration first. Tap a meal to open its recipe in Dishes.

```yaml
type: custom:dishes-week-card
title: This Week's Meals          # optional
meal_types: [breakfast, lunch, dinner]   # optional
show_times: true                  # optional
entity: sensor.dishes_week_plan_status   # optional, found automatically
```

> **Upgrading from 1.x:** the card no longer takes a `url` or `token` — it used to keep the token in the dashboard config, where anyone who could open the dashboard could read it. Remove both from the card's config (the card reminds you), and revoke that token in Dishes if nothing else uses it.

---

## Integration Setup

1. In Dishes, go to **Settings → Integrations** and create a token. Give it the scopes for what you want in Home Assistant:
   - `read:meal_plan` — required: meals, dinner times, deliveries, calendar
   - `read:cooking` — who's cooking, cooking step, timers
   - `read:shopping_list` and `write:shopping_list` — the shopping list to-do
2. In HA go to **Settings → Devices & Services → Add Integration** and search for **Dishes**
3. Enter your Dishes app URL (e.g. `https://dishes.home.example.com`) and the token

**Adding scopes later** — use **Reconfigure** on the integration with a new token (or reload it after changing the token's scopes in Dishes); the new entities appear.

**Token revoked or expired** — Home Assistant asks for a new one (a "Reconfigure" notice on the integration) instead of the entities quietly going unavailable.

**Options** — how often to fetch the meal plan (default 30 minutes) and to check who's cooking (default 30 seconds).

Needs Dishes 1.54 or later for cooking, the shopping list to-do, dinner times and the household timezone. With an older Dishes the meal sensors still work, with the assumed meal times above.

---

## Example Automations

**Notify at 5pm with tonight's dinner** (skipped when nothing's planned):

```yaml
triggers:
  - trigger: time
    at: "17:00:00"
conditions:
  - condition: template
    value_template: "{{ has_value('sensor.dishes_tonight_s_dinner') }}"
actions:
  - action: notify.mobile_app_phone
    data:
      message: "Tonight's dinner: {{ states('sensor.dishes_tonight_s_dinner') }}"
```

**Time to start cooking** — fires when Dishes says to start, for the household's dinner time:

```yaml
triggers:
  - trigger: time
    at: sensor.dishes_start_cooking
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.kitchen
      message: "Time to start cooking {{ states('sensor.dishes_tonight_s_dinner') }}."
```

**Flash the kitchen lights when a cooking timer ends:**

```yaml
triggers:
  - trigger: time
    at: sensor.dishes_next_timer
actions:
  - action: light.turn_on
    target:
      entity_id: light.kitchen
    data:
      flash: short
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.kitchen
      message: "{{ state_attr('sensor.dishes_next_timer', 'label') }} timer is done."
```

**Kitchen lights up while someone's cooking:**

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.dishes_cooking
    to: "on"
actions:
  - action: light.turn_on
    target:
      entity_id: light.kitchen
    data:
      brightness_pct: 100
```

**An hour before any meal** — a calendar trigger with an offset:

```yaml
triggers:
  - trigger: calendar
    event: start
    entity_id: calendar.dishes_meal_plan
    offset: "-1:00:00"
actions:
  - action: notify.mobile_app_phone
    data:
      message: "In an hour: {{ trigger.calendar_event.summary }}"
```

**Order the groceries reminder:**

```yaml
triggers:
  - trigger: time
    at: sensor.dishes_order_deadline
    offset: "-03:00:00"
conditions:
  - condition: state
    entity_id: sensor.dishes_order_deadline
    attribute: ordered
    state: false
actions:
  - action: notify.mobile_app_phone
    data:
      message: "Grocery order closes in 3 hours."
```

**Announce the next meal on a speaker:**

```yaml
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.kitchen
      message: >
        The next meal is {{ states('sensor.dishes_next_meal') }},
        {{ state_attr('sensor.dishes_next_meal', 'meal_type') }}
        on {{ state_attr('sensor.dishes_next_meal', 'day_of_week') }}.
```

---

## Requirements

- Dishes 1.54 or later for every entity (older versions: meal sensors only)
- Home Assistant 2024.11.0 or later

## Development

```bash
pip install -r requirements_test.txt
pytest
```
