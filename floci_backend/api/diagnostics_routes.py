from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any

from floci_backend.application.diagnostics_service import DiagnosticsService

def create_diagnostics_router(diagnostics_service: DiagnosticsService) -> APIRouter:
    router = APIRouter()

    @router.get('/diagnostics/kms')
    async def run_kms_diagnostic():
        result = await diagnostics_service.run_kms_round_trip()
        status_code = 200 if result.get('ok') else 502
        return JSONResponse(status_code=status_code, content=result)

    @router.get('/diagnostics/cost-forecast')
    async def run_cost_forecast():
        result = await diagnostics_service.run_cost_forecast()
        status_code = 200 if result.get('ok') else 500
        return JSONResponse(status_code=status_code, content=result)

    return router
