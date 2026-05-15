from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_URL
from .coordinator import DishesCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DishesCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DishesNextMealSensor(coordinator, entry),
            DishesTodayMealSensor(coordinator, entry, "dinner", "Tonight's Dinner"),
            DishesTodayMealSensor(coordinator, entry, "lunch", "Today's Lunch"),
            DishesTodayMealSensor(coordinator, entry, "breakfast", "Today's Breakfast"),
            DishesWeekPlanSensor(coordinator, entry),
        ]
    )


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Dishes",
        manufacturer="Dishes",
        model="Meal Planner",
        configuration_url=entry.data[CONF_URL],
    )


class DishesNextMealSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, coordinator: DishesCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_next_meal"
        self._attr_name = "Next Meal"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        entry = self.coordinator.get_next_meal()
        return entry["recipe"]["title"] if entry else None

    @property
    def extra_state_attributes(self) -> dict:
        entry = self.coordinator.get_next_meal()
        if not entry:
            return {}
        return self.coordinator.entry_attributes(entry)


class DishesTodayMealSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:food"

    def __init__(
        self,
        coordinator: DishesCoordinator,
        entry: ConfigEntry,
        meal_type: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._meal_type = meal_type
        self._attr_unique_id = f"{entry.entry_id}_today_{meal_type}"
        self._attr_name = name
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        meal = self.coordinator.get_today_meal(self._meal_type)
        return meal["recipe"]["title"] if meal else None

    @property
    def extra_state_attributes(self) -> dict:
        meal = self.coordinator.get_today_meal(self._meal_type)
        if not meal:
            return {}
        attrs = self.coordinator.entry_attributes(meal)
        # day_of_week is redundant for "today" sensors
        attrs.pop("day_of_week", None)
        return attrs


class DishesWeekPlanSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator: DishesCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_week_plan"
        self._attr_name = "Week Plan Status"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str:
        if not self.coordinator.data:
            return "unavailable"
        return self.coordinator.data.get("planStatus", "none")

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        entries = self.coordinator.data.get("entries", [])
        return {
            "week_start": self.coordinator.data.get("weekStartDate"),
            "meal_count": len(entries),
        }
