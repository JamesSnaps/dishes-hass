from __future__ import annotations

from datetime import time, timedelta

DOMAIN = "dishes"

CONF_URL = "url"
CONF_TOKEN = "token"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_COOKING_INTERVAL = "cooking_interval"

DEFAULT_SCAN_INTERVAL = 30  # minutes — the meal plan changes rarely
DEFAULT_COOKING_INTERVAL = 30  # seconds — "who's cooking" should feel live
SHOPPING_SCAN_INTERVAL = timedelta(minutes=2)

# Token scopes (Dishes → Settings → Integrations). read:meal_plan is required;
# the rest each switch on more entities.
SCOPE_MEAL_PLAN = "read:meal_plan"
SCOPE_COOKING = "read:cooking"
SCOPE_SHOPPING_READ = "read:shopping_list"
SCOPE_SHOPPING_WRITE = "write:shopping_list"

# When a meal is eaten if Dishes has no serve time for it, on the household's
# clock. Dinner normally comes with one (the household's dinner time).
MEAL_DEFAULT_TIME: dict[str, time] = {
    "breakfast": time(8, 0),
    "lunch": time(12, 30),
    "snack": time(15, 30),
    "dinner": time(18, 0),
    "dessert": time(19, 30),
}

# A meal stays "next" (and its calendar event lasts) this long after it's served.
MEAL_DURATION = timedelta(hours=1)

MEAL_LABELS: dict[str, str] = {
    "breakfast": "Breakfast",
    "lunch": "Lunch",
    "snack": "Snack",
    "dinner": "Dinner",
    "dessert": "Dessert",
}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
