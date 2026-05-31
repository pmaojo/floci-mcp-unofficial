"""Pipeline MCP tools — deploy marketplace recipes to test/demo and generate production manifests."""
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def list_pipeline_environments() -> dict:
        """
        Lista los entornos del pipeline (test, demo, production) con el estado de cada recipe
        desplegada en cada uno.

        Úsalo para ver qué está corriendo en cada entorno antes de desplegar o promover.
        """
        return await backend("GET", "/api/pipeline/environments")

    @mcp.tool()
    async def deploy_to_environment(recipe_id: str, env: str, vars: dict | None = None) -> dict:
        """
        Despliega una recipe del marketplace en el entorno especificado (test o demo).

        Los puertos se ajustan automáticamente para evitar conflictos:
        - test: puerto base + 10000 (ej. postgres → 15432)
        - demo: puerto base + 20000 (ej. postgres → 25432)

        recipe_id: ID de la recipe (ej. 'postgres', 'redis', 'n8n').
        env: 'test' o 'demo'.
        vars: variables de configuración opcionales. Si se omiten, se usan los valores por defecto.
        """
        return await backend("POST", "/api/pipeline/deploy", json_data={
            "recipeId": recipe_id,
            "env": env,
            "vars": vars or {},
        })

    @mcp.tool()
    async def teardown_environment_recipe(recipe_id: str, env: str) -> dict:
        """
        Para y elimina una recipe desplegada en un entorno específico (test o demo).

        recipe_id: ID de la recipe.
        env: 'test' o 'demo'.
        """
        return await backend("DELETE", f"/api/pipeline/deploy/{env}/{recipe_id}")

    @mcp.tool()
    async def promote_recipe(recipe_id: str, from_env: str, to_env: str) -> dict:
        """
        Promueve una recipe de un entorno al siguiente.

        El flujo estándar es: test → demo → production.
        Para promover a production, usa generate_copilot_manifests() y aplica con
        'copilot deploy' o 'terraform apply'.

        recipe_id: ID de la recipe (ej. 'postgres').
        from_env: entorno origen ('test' o 'demo').
        to_env: entorno destino ('demo').
        """
        return await backend("POST", "/api/pipeline/promote", json_data={
            "recipeId": recipe_id,
            "fromEnv": from_env,
            "toEnv": to_env,
        })

    @mcp.tool()
    async def generate_copilot_manifests(recipe_id: str) -> dict:
        """
        Genera los manifests de AWS Copilot para desplegar una recipe en ECS/Fargate.

        Para recipes con equivalente AWS gestionado (postgres → RDS, redis → ElastiCache),
        usa export_recipes_to_terraform() en su lugar.

        Para recipes que se despliegan en contenedores (n8n, metabase, temporal, airflow, etc.)
        este tool genera los archivos copilot/services/{recipe}/manifest.yml y
        copilot/environments/{env}/manifest.yml listos para aplicar con:
            copilot svc deploy --name {recipe_id} --env production

        recipe_id: ID de la recipe.
        """
        return await backend("GET", f"/api/pipeline/manifests/{recipe_id}")

    @mcp.tool()
    async def get_pipeline_logs(recipe_id: str, env: str) -> dict:
        """
        Obtiene los logs de Docker Compose de una recipe en un entorno del pipeline.

        recipe_id: ID de la recipe.
        env: 'test' o 'demo'.
        """
        return await backend("GET", f"/api/pipeline/logs/{env}/{recipe_id}")
