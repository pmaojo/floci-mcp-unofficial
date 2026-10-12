"""Pipeline MCP tools — deploy marketplace recipes to test/demo and generate production manifests."""
from floci_tools._client import backend


def register(mcp):

    @mcp.tool()
    async def list_pipeline_environments() -> dict:
        """
        Lists the pipeline environments (test, demo, production) with the state of each
        recipe deployed in each one.

        Use it to see what is running in each environment before deploying or promoting.
        """
        return await backend("GET", "/api/pipeline/environments")

    @mcp.tool()
    async def deploy_to_environment(recipe_id: str, env: str, vars: dict | None = None) -> dict:
        """
        Deploys a marketplace recipe to a pipeline environment (test or demo).

        Ports are shifted automatically to avoid conflicts:
        - test: base port + 10000 (e.g. postgres -> 15432)
        - demo: base port + 20000 (e.g. postgres -> 25432)

        recipe_id: recipe ID (e.g. 'postgres', 'redis', 'n8n').
        env: 'test' or 'demo'.
        vars: optional configuration variables. Defaults are used when omitted.
        """
        return await backend("POST", "/api/pipeline/deploy", json_data={
            "recipeId": recipe_id,
            "env": env,
            "vars": vars or {},
        })

    @mcp.tool()
    async def teardown_environment_recipe(recipe_id: str, env: str) -> dict:
        """
        Stops and removes a recipe deployed in a pipeline environment (test or demo).

        recipe_id: recipe ID.
        env: 'test' or 'demo'.
        """
        return await backend("DELETE", f"/api/pipeline/deploy/{env}/{recipe_id}")

    @mcp.tool()
    async def promote_recipe(recipe_id: str, from_env: str, to_env: str) -> dict:
        """
        Promotes a recipe from one pipeline environment to the next.

        The standard flow is test -> demo -> production. To promote to production use
        generate_copilot_manifests() and apply with 'copilot deploy' or 'terraform apply'.

        recipe_id: recipe ID (e.g. 'postgres').
        from_env: source environment ('test' or 'demo').
        to_env: target environment ('demo').
        """
        return await backend("POST", "/api/pipeline/promote", json_data={
            "recipeId": recipe_id,
            "fromEnv": from_env,
            "toEnv": to_env,
        })

    @mcp.tool()
    async def generate_copilot_manifests(recipe_id: str) -> dict:
        """
        Generates AWS Copilot manifests to deploy a recipe on ECS/Fargate.

        For recipes that have a managed AWS equivalent (postgres -> RDS, redis -> ElastiCache)
        use export_recipes_to_terraform() instead.

        For container recipes (n8n, metabase, temporal, airflow, ...) it generates
        copilot/services/{recipe}/manifest.yml and copilot/environments/{env}/manifest.yml,
        ready to apply with: copilot svc deploy --name {recipe_id} --env production

        recipe_id: recipe ID.
        """
        return await backend("GET", f"/api/pipeline/manifests/{recipe_id}")

    @mcp.tool()
    async def get_pipeline_logs(recipe_id: str, env: str) -> dict:
        """
        Gets the Docker Compose logs of a recipe in a pipeline environment.

        recipe_id: recipe ID.
        env: 'test' or 'demo'.
        """
        return await backend("GET", f"/api/pipeline/logs/{env}/{recipe_id}")
