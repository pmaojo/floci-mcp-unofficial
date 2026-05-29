"""Herramientas Marketplace: recetas de software local en Docker."""
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def list_marketplace_recipes() -> dict:
        """
        Lista todas las recetas del Marketplace con sus variables configurables.

        Recetas disponibles: postgres, redis, mongodb, rabbitmq, keycloak, mailpit,
        minio, redpanda, observability, jaeger, meilisearch, pocketbase, nginx-proxy-manager, etc.
        """
        return await backend("GET", "/api/marketplace/recipes")

    @mcp.tool()
    async def get_marketplace_installations() -> dict:
        """
        Obtiene el estado de todas las instalaciones del Marketplace.

        Estados posibles: IDLE, INSTALLING, RUNNING, UNINSTALLING, FAILED.
        """
        return await backend("GET", "/api/marketplace/installations")

    @mcp.tool()
    async def get_marketplace_logs(recipe_id: str) -> dict:
        """
        Obtiene los logs de Docker Compose de una receta del Marketplace.

        Útil para diagnosticar fallos durante la instalación o ejecución.
        """
        return await backend("GET", f"/api/marketplace/recipes/{recipe_id}/logs")

    @mcp.tool()
    async def deploy_marketplace_app(recipe_id: str, vars: dict | None = None) -> dict:
        """
        Instala y arranca una receta del Marketplace en Docker local.

        vars contiene las variables de configuración de la receta (puertos, contraseñas, etc.).
        Usa list_marketplace_recipes para conocer las variables disponibles.
        Ejemplo: deploy_marketplace_app('postgres', {'POSTGRES_PASSWORD': 'secret', 'POSTGRES_PORT': 5432})
        """
        return await backend("POST", "/api/marketplace/install", json_data={"recipeId": recipe_id, "vars": vars or {}})

    @mcp.tool()
    async def teardown_marketplace_app(recipe_id: str) -> dict:
        """Detiene y elimina los contenedores y volúmenes de una receta del Marketplace."""
        return await backend("DELETE", f"/api/marketplace/install/{recipe_id}")
