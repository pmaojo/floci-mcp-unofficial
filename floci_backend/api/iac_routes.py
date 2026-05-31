from fastapi import APIRouter, HTTPException

from floci_backend.application.drift_service import DriftService


def create_iac_router(drift_service: DriftService) -> APIRouter:
    router = APIRouter()

    @router.get("/iac/discover")
    async def discover(path: str = "."):
        try:
            return drift_service.discover(path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/iac/drift")
    async def drift(path: str = "."):
        try:
            return drift_service.detect_drift(path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
