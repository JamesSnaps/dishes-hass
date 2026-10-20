"""Client for the Dishes integrations API (API.md in the dishes-app repo)."""

from __future__ import annotations

from datetime import date
from typing import Any

import aiohttp

from .const import SCOPE_MEAL_PLAN

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class DishesError(Exception):
    """Dishes couldn't answer."""


class DishesConnectionError(DishesError):
    """Dishes couldn't be reached."""


class DishesAuthError(DishesError):
    """The token is invalid, revoked or expired (401)."""


class DishesScopeError(DishesError):
    """The token is valid but lacks the endpoint's scope (403)."""


class DishesNotFoundError(DishesError):
    """No such endpoint or item (404)."""


class DishesApi:
    """The integrations API, authenticated with a household token."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self.url = url.rstrip("/")
        self._token = token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Any = None,
    ) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self.url}/api/integrations/{path}",
                params=params,
                json=json,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise DishesAuthError("Invalid or expired integration token")
                if resp.status == 403:
                    raise DishesScopeError(f"Token is missing the scope for {path}")
                if resp.status == 404:
                    raise DishesNotFoundError(f"{path} not found (is Dishes up to date?)")
                if resp.status == 429:
                    raise DishesError("Rate limited by Dishes")
                if resp.status >= 400:
                    raise DishesError(f"Unexpected response from {path}: {resp.status}")
                return await resp.json()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise DishesConnectionError(f"Can't reach Dishes: {err}") from err

    async def token_info(self) -> dict[str, Any]:
        """The token's name, household and scopes.

        Dishes before 1.54 has no token endpoint: the meal plan is then the
        one thing known to work, which is what this integration always needed.
        """
        try:
            return await self._request("GET", "token")
        except DishesNotFoundError:
            await self.week()
            return {"name": None, "household": None, "scopes": [SCOPE_MEAL_PLAN]}

    async def today(self) -> dict[str, Any]:
        return await self._request("GET", "today")

    async def week(self, week: date | None = None) -> dict[str, Any]:
        params = {"week": week.isoformat()} if week else None
        return await self._request("GET", "meal-plan/week", params=params)

    async def cooking(self) -> dict[str, Any]:
        return await self._request("GET", "cooking")

    async def shopping_list(self) -> dict[str, Any]:
        return await self._request("GET", "shopping-list")

    async def quick_add_shopping_item(self, text: str) -> dict[str, Any]:
        return await self._request("POST", "shopping-list/quick-add", json={"text": text})

    async def update_shopping_item(self, item_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", f"shopping-list/items/{item_id}", json=changes)

    async def delete_shopping_item(self, item_id: str) -> dict[str, Any]:
        return await self._request("DELETE", f"shopping-list/items/{item_id}")

    def recipe_url(self, recipe_id: str) -> str:
        return f"{self.url}/recipes/{recipe_id}"

    def cook_url(self, recipe_id: str) -> str:
        return f"{self.url}/recipes/{recipe_id}/cook"
