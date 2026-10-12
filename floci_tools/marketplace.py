"""Marketplace: local Docker recipes, three tools.

Reading is one tool; starting and removing are separate, so FLOCI_READ_ONLY removes
the writers. The same operations are reachable with no extra tool definitions through
the generic toolset (cloud="recipes"); this toolset is for clients that prefer named tools.
"""
from floci_generic import bootstrap


async def _call(operation: str, params: dict) -> dict:
    """A failure is a tool error (isError) for these named tools, as it was before recipes moved to the gateway."""
    out = await bootstrap.recipe_service.call(operation, params)
    if "error" in out:
        raise RuntimeError(out["error"])
    return out


def register(mcp):

    @mcp.tool()
    async def list_marketplace_recipes(recipe_id: str = "", status: bool = False, logs: bool = False) -> dict:
        """
        Lists the Docker recipes (postgres, redis, kafka, keycloak, ollama...), or details one.

        Each recipe says which AWS service it stands in for and floci_native when Floci emulates that
        service itself: prefer that one. With recipe_id you get its variables and defaults. status=true
        adds the state of installed recipes (IDLE, INSTALLING, RUNNING, UNINSTALLING, FAILED) with the
        access URL; logs=true adds the last lines of that recipe's output.
        """
        out = await _call("GetRecipe" if recipe_id else "ListRecipes", {"recipe_id": recipe_id})
        if status or logs:
            out["installed"] = (await _call("GetStatus", {"recipe_id": recipe_id}))["installed"]
        if logs and recipe_id:
            out["log_lines"] = (await _call("GetLogs", {"recipe_id": recipe_id}))["lines"]
        return out

    @mcp.tool()
    async def deploy_marketplace_app(recipe_id: str, vars: dict | None = None, wait_seconds: int = 90) -> dict:
        """
        Starts a recipe on local Docker and waits until it is RUNNING or FAILED.

        Returns the access URL. A default port that is already taken is moved to a free one and reported;
        a port you set yourself that is taken is refused with a suggestion. vars are the recipe's variables.
        Example: deploy_marketplace_app('postgres', {'POSTGRES_PASSWORD': 'secret'})
        """
        return await _call("DeployRecipe", {"recipe_id": recipe_id, "vars": vars or {}, "wait_seconds": wait_seconds})

    @mcp.tool()
    async def teardown_marketplace_app(recipe_id: str, wait_seconds: int = 60) -> dict:
        """Stops a recipe and removes its containers AND volumes (its data). Confirm with the user first."""
        return await _call("TeardownRecipe", {"recipe_id": recipe_id, "wait_seconds": wait_seconds})
