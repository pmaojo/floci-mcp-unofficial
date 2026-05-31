from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from floci_backend.application.pipeline_service import PipelineService
from floci_backend.application.recipe_service import RecipeService


def create_pipeline_router(pipeline_service: PipelineService, recipe_service: RecipeService) -> APIRouter:
    router = APIRouter()

    async def _get_recipe(recipe_id: str) -> Dict[str, Any]:
        recipes = await recipe_service.list_recipes()
        recipe = next((r for r in recipes if r['id'] == recipe_id), None)
        if not recipe:
            raise HTTPException(status_code=404, detail=f'Recipe {recipe_id} not found')
        return recipe

    @router.get('/pipeline/environments')
    async def list_environments():
        try:
            return {'ok': True, 'environments': await pipeline_service.list_environments()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post('/pipeline/deploy')
    async def deploy(request: Dict[str, Any]):
        try:
            recipe_id = request.get('recipeId')
            env = request.get('env')
            vars_data = request.get('vars', {})
            if not recipe_id or not env:
                raise ValueError('recipeId and env are required')
            recipe_meta = await _get_recipe(recipe_id)
            inst = await pipeline_service.deploy(recipe_id, env, vars_data, recipe_meta)
            return {'ok': True, 'installation': inst}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.delete('/pipeline/deploy/{env}/{recipe_id}')
    async def teardown(env: str, recipe_id: str):
        try:
            inst = await pipeline_service.teardown(recipe_id, env)
            return {'ok': True, 'installation': inst}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post('/pipeline/promote')
    async def promote(request: Dict[str, Any]):
        try:
            recipe_id = request.get('recipeId')
            from_env = request.get('fromEnv')
            to_env = request.get('toEnv')
            if not all([recipe_id, from_env, to_env]):
                raise ValueError('recipeId, fromEnv and toEnv are required')
            recipe_meta = await _get_recipe(recipe_id)
            inst = await pipeline_service.promote(recipe_id, from_env, to_env, recipe_meta)
            return {'ok': True, 'installation': inst}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get('/pipeline/logs/{env}/{recipe_id}')
    async def get_logs(env: str, recipe_id: str):
        try:
            logs = await pipeline_service.get_logs(recipe_id, env)
            return {'ok': True, 'logs': logs}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get('/pipeline/manifests/{recipe_id}')
    async def get_manifests(recipe_id: str):
        try:
            recipe_meta = await _get_recipe(recipe_id)
            manifests = pipeline_service.generate_copilot_manifests(recipe_id, recipe_meta)
            return {'ok': True, 'manifests': manifests, 'hasCopilot': bool(manifests)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
