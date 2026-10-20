from __future__ import annotations

from collections.abc import Coroutine
from contextlib import suppress
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DishesConfigEntry
from .api import DishesError, DishesNotFoundError
from .const import SCOPE_SHOPPING_WRITE
from .coordinator import ShoppingCoordinator
from .entity import DishesEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DishesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    if data.shopping:
        async_add_entities(
            [ShoppingListTodo(data.shopping, entry, SCOPE_SHOPPING_WRITE in data.scopes)]
        )


def _description(item: dict[str, Any]) -> str | None:
    amount = " ".join(p for p in (item.get("amount"), item.get("unit")) if p)
    return amount or None


class ShoppingListTodo(DishesEntity, TodoListEntity):
    """The household's active shopping list.

    With write:shopping_list it's two-way: add items (by voice through Assist,
    too), tick them off, rename and remove them. Read-only without it.
    """

    coordinator: ShoppingCoordinator
    _attr_translation_key = "shopping_list"
    _attr_icon = "mdi:cart-outline"

    def __init__(
        self, coordinator: ShoppingCoordinator, entry: DishesConfigEntry, writable: bool
    ) -> None:
        super().__init__(coordinator, entry, "shopping_list")
        if writable:
            self._attr_supported_features = (
                TodoListEntityFeature.CREATE_TODO_ITEM
                | TodoListEntityFeature.UPDATE_TODO_ITEM
                | TodoListEntityFeature.DELETE_TODO_ITEM
            )

    @property
    def todo_items(self) -> list[TodoItem] | None:
        if self.coordinator.data is None:
            return None
        return [
            TodoItem(
                summary=item["ingredientName"],
                uid=item["id"],
                status=TodoItemStatus.COMPLETED if item["isChecked"] else TodoItemStatus.NEEDS_ACTION,
                description=_description(item),
            )
            for item in self.coordinator.data.get("items", [])
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        # Quick-add keeps the text as said: "2 pints of milk".
        await self._write(self.coordinator.api.quick_add_shopping_item(item.summary or ""))

    async def async_update_todo_item(self, item: TodoItem) -> None:
        current = next(
            (i for i in self.coordinator.data.get("items", []) if i["id"] == item.uid), None
        )
        if current is None:
            raise HomeAssistantError("That item is no longer on the shopping list")
        changes: dict[str, Any] = {}
        if item.summary and item.summary != current["ingredientName"]:
            changes["ingredientName"] = item.summary
        if item.status is not None:
            checked = item.status == TodoItemStatus.COMPLETED
            if checked != current["isChecked"]:
                changes["isChecked"] = checked
        if changes:
            await self._write(self.coordinator.api.update_shopping_item(item.uid, changes))

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        try:
            for uid in uids:
                # Already gone — removed in Dishes since the last poll — is fine.
                with suppress(DishesNotFoundError):
                    await self.coordinator.api.delete_shopping_item(uid)
        except DishesError as err:
            raise HomeAssistantError(f"Dishes didn't take the change: {err}") from err
        finally:
            await self.coordinator.async_refresh()

    async def _write(self, call: Coroutine[Any, Any, Any]) -> None:
        try:
            await call
        except DishesError as err:
            raise HomeAssistantError(f"Dishes didn't take the change: {err}") from err
        await self.coordinator.async_refresh()
