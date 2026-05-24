from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional

from floci_backend.application.athena_service import AthenaService

def create_athena_router(athena_service: AthenaService) -> APIRouter:
    router = APIRouter()

    @router.get('/athena/catalog')
    async def get_catalog() -> Dict[str, Any]:
        try:
            catalog = await athena_service.get_catalog()
            return {'ok': True, 'catalog': catalog}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.post('/athena/query')
    async def start_query(request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            query = request.get('query')
            database = request.get('database')
            work_group = request.get('workGroup', 'primary')

            if not query or not database:
                raise ValueError("query and database are required")

            result = await athena_service.start_query(query, database, work_group)
            return {'ok': True, **result}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.get('/athena/query/{execution_id}')
    async def get_query_status(execution_id: str) -> Dict[str, Any]:
        try:
            execution = await athena_service.get_query_status(execution_id)
            return {'ok': True, 'execution': execution}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.get('/athena/query/{execution_id}/results')
    async def get_query_results(execution_id: str) -> Dict[str, Any]:
        try:
            results = await athena_service.get_query_results(execution_id)
            return {'ok': True, 'results': results}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.get('/athena/history')
    async def get_history() -> Dict[str, Any]:
        try:
            history = await athena_service.get_history()
            return {'ok': True, 'history': history}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    @router.delete('/athena/history')
    async def clear_history() -> Dict[str, Any]:
        try:
            await athena_service.clear_history()
            return {'ok': True}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    return router
