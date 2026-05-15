DOMAIN = "dishes"

CONF_URL = "url"
CONF_TOKEN = "token"

DEFAULT_SCAN_INTERVAL = 30  # minutes

# Approximate hour-of-day for each meal type — used to determine "next" meal
MEAL_TIME_HOUR: dict[str, int] = {
    "breakfast": 8,
    "lunch": 12,
    "snack": 15,
    "dinner": 18,
    "dessert": 20,
}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
