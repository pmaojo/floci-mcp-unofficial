from fastapi import APIRouter
from typing import Dict, Any

from floci_backend.application.eks_service import EksService

def create_eks_router(eks_service: EksService) -> APIRouter:
    router = APIRouter()

    @router.get('/eks/overview')
    async def get_overview() -> Dict[str, Any]:
        return await eks_service.get_overview()

    return router
