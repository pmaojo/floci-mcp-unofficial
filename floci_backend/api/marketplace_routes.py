from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional

from floci_backend.application.recipe_service import RecipeService

def create_marketplace_router(recipe_service: RecipeService) -> APIRouter:
    router = APIRouter()

    @router.get('/marketplace/recipes')
    async def list_recipes() -> Dict[str, Any]:
        try:
            recipes = await recipe_service.list_recipes()
            return {'ok': True, 'recipes': recipes}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.get('/marketplace/installations')
    async def get_installations() -> Dict[str, Any]:
        try:
            installations = await recipe_service.get_installations()
            return {'ok': True, 'installations': installations}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.get('/marketplace/recipes/{recipe_id}/logs')
    async def get_logs(recipe_id: str) -> Dict[str, Any]:
        try:
            logs = await recipe_service.get_logs(recipe_id)
            return {'ok': True, 'logs': logs}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.post('/marketplace/install')
    async def install_recipe(request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            recipe_id = request.get('recipeId')
            vars_data = request.get('vars', {})
            if not recipe_id:
                raise ValueError('recipeId is required')
            installation = await recipe_service.install_recipe(recipe_id, vars_data)
            return {'ok': True, 'installation': installation}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.delete('/marketplace/install/{recipe_id}')
    async def uninstall_recipe(recipe_id: str) -> Dict[str, Any]:
        try:
            installation = await recipe_service.uninstall_recipe(recipe_id)
            return {'ok': True, 'installation': installation}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    return router
