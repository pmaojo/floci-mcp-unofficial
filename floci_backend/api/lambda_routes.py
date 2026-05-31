from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from floci_backend.application.lambda_service import LambdaService

def create_lambda_router(lambda_service: LambdaService) -> APIRouter:
    router = APIRouter()

    @router.get('/lambda/capabilities')
    async def get_capabilities() -> Dict[str, Any]:
        return await lambda_service.get_capabilities()

    @router.get('/lambda/functions')
    async def list_functions() -> Dict[str, Any]:
        result = await lambda_service.list_functions()
        return {'ok': True, **result}

    @router.post('/lambda/functions')
    async def create_function(request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await lambda_service.create_function(request)
            return {'ok': True, **result}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.put('/lambda/functions/{function_name}/code')
    async def update_function_code(function_name: str, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await lambda_service.update_function_code(function_name, request)
            return {'ok': True, **result}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.put('/lambda/functions/{function_name}/configuration')
    async def update_function_configuration(function_name: str, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await lambda_service.update_function_configuration(function_name, request)
            return {'ok': True, **result}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.post('/lambda/functions/{function_name}/invoke')
    async def invoke_function(function_name: str, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await lambda_service.invoke_function(function_name, request)
            return {'ok': True, **result}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.delete('/lambda/functions/{function_name}')
    async def delete_function(function_name: str) -> Dict[str, Any]:
        try:
            result = await lambda_service.delete_function(function_name)
            return {'ok': True, **result}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.get('/lambda/functions/{function_name}/logs')
    async def get_logs(function_name: str) -> Dict[str, Any]:
        try:
            result = await lambda_service.get_logs(function_name)
            return {'ok': True, **result}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    return router
