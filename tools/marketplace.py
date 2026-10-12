"""Herramientas Marketplace: recetas de software local en Docker."""
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def list_marketplace_recipes() -> dict:
        """
        Lists every Marketplace recipe with its configurable variables.

        Recipes include postgres, redis, mongodb, rabbitmq, keycloak, mailpit, minio, redpanda,
        observability, jaeger, meilisearch, pocketbase, nginx-proxy-manager, dynamodb-admin,
        n8n, temporal, nats, kafka, ollama and more. Use it before deploy_marketplace_app.
        """
        return await backend("GET", "/api/marketplace/recipes")

    @mcp.tool()
    async def get_marketplace_installations() -> dict:
        """
        Gets the state of every Marketplace installation.

        Possible states: IDLE, INSTALLING, RUNNING, UNINSTALLING, FAILED.
        """
        return await backend("GET", "/api/marketplace/installations")

    @mcp.tool()
    async def get_marketplace_logs(recipe_id: str) -> dict:
        """
        Gets the Docker Compose logs of a Marketplace recipe.

        Useful to diagnose failures during installation or while running.
        """
        return await backend("GET", f"/api/marketplace/recipes/{recipe_id}/logs")

    @mcp.tool()
    async def deploy_marketplace_app(recipe_id: str, vars: dict | None = None) -> dict:
        """
        Installs and starts a Marketplace recipe on local Docker.

        vars holds the recipe's configuration variables (ports, passwords, ...).
        Use list_marketplace_recipes to see the available variables.
        Example: deploy_marketplace_app('postgres', {'POSTGRES_PASSWORD': 'secret', 'POSTGRES_PORT': 5432})
        """
        return await backend("POST", "/api/marketplace/install", json_data={"recipeId": recipe_id, "vars": vars or {}})

    @mcp.tool()
    async def teardown_marketplace_app(recipe_id: str) -> dict:
        """Stops and removes the containers and volumes of a Marketplace recipe."""
        return await backend("DELETE", f"/api/marketplace/install/{recipe_id}")
