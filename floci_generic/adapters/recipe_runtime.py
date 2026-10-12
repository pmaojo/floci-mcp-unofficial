"""Recipes on this machine: the in-process backend (docker compose), the host's ports, and Floci."""
import os
import socket
from typing import Any, Callable

import httpx


class InProcessRecipeRuntime:
    """Implements ports.RecipeRuntime through the FastAPI backend that ships in this package."""

    def __init__(self, answering: Callable[[list[str]], set[str]]) -> None:
        self._answering = answering

    async def _backend(self, method: str, path: str, json_data: dict | None = None) -> Any:
        from floci_backend.server import app

        headers = {}
        token = os.environ.get("SIDECAR_TOKEN")
        if token:
            headers["x-floci-sidecar-token"] = token
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.request(method, path, headers=headers, json=json_data)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} failed with HTTP {response.status_code}: {response.text[:400]}")
        return response.json()

    async def recipes(self) -> list[dict]:
        """Every recipe in the catalog."""
        return (await self._backend("GET", "/api/marketplace/recipes")).get("recipes", [])

    async def installations(self) -> dict:
        """recipe id -> its installation state."""
        return (await self._backend("GET", "/api/marketplace/installations")).get("installations", {})

    async def logs(self, recipe_id: str) -> list[str]:
        """The Docker Compose output kept for a recipe."""
        return (await self._backend("GET", f"/api/marketplace/recipes/{recipe_id}/logs")).get("logs", [])

    async def install(self, recipe_id: str, variables: dict) -> None:
        """Start an installation (it continues in the background)."""
        await self._backend("POST", "/api/marketplace/install", {"recipeId": recipe_id, "vars": variables})

    async def uninstall(self, recipe_id: str) -> None:
        """Start removing a recipe's containers and volumes."""
        await self._backend("DELETE", f"/api/marketplace/install/{recipe_id}")

    def port_busy(self, port: int) -> bool:
        """Whether something already listens on this port of localhost."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.3)
            return probe.connect_ex(("127.0.0.1", port)) == 0

    def answering_aws(self, services: list[str]) -> set[str]:
        """Which of these AWS services answer on the running Floci."""
        return self._answering(services)
