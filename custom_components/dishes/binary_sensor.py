from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DishesConfigEntry
from .coordinator import CookingCoordinator
from .entity import DishesEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DishesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    cooking = entry.runtime_data.cooking
    if not cooking:
        return

    async_add_entities([CookingBinarySensor(cooking, entry)])

    # One "is cooking" sensor per household member, added as members join.
    known: set[str] = set()

    @callback
    def add_members() -> None:
        new = [m for m in cooking.members if m["id"] not in known]
        known.update(m["id"] for m in new)
        if new:
            async_add_entities(MemberCookingBinarySensor(cooking, entry, m) for m in new)

    add_members()
    entry.async_on_unload(cooking.async_add_listener(add_members))


class CookingBinarySensor(DishesEntity, BinarySensorEntity):
    """On while anyone in the household is in cooking mode."""

    coordinator: CookingCoordinator
    _attr_translation_key = "cooking"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: CookingCoordinator, entry: DishesConfigEntry) -> None:
        super().__init__(coordinator, entry, "cooking")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.sessions)

    @property
    def icon(self) -> str:
        return "mdi:stove" if self.is_on else "mdi:stove-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sessions = self.coordinator.sessions
        return {
            "cooks": sorted({s["memberName"] for s in sessions}),
            "meals": [s["title"] for s in sessions],
        }


class MemberCookingBinarySensor(DishesEntity, BinarySensorEntity):
    """On while one household member is in cooking mode."""

    coordinator: CookingCoordinator
    _attr_translation_key = "member_cooking"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self, coordinator: CookingCoordinator, entry: DishesConfigEntry, member: dict[str, Any]
    ) -> None:
        super().__init__(coordinator, entry, f"cooking_{member['id']}")
        self._member_id = member["id"]
        self._attr_translation_placeholders = {"name": member["name"]}

    @property
    def _sessions(self) -> list[dict[str, Any]]:
        return [s for s in self.coordinator.sessions if s["memberId"] == self._member_id]

    @property
    def available(self) -> bool:
        # A member who has left the household: unavailable rather than "off".
        return super().available and any(
            m["id"] == self._member_id for m in self.coordinator.members
        )

    @property
    def is_on(self) -> bool:
        return bool(self._sessions)

    @property
    def icon(self) -> str:
        return "mdi:chef-hat" if self.is_on else "mdi:account-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        session = max(self._sessions, key=lambda s: s["updatedAt"], default=None)
        if not session:
            return {}
        return {
            "meal": session["title"],
            "dish": session["dish"],
            "step": session["step"],
            "total_steps": session["totalSteps"],
            "device": session["device"],
            "started_at": session["startedAt"],
        }
