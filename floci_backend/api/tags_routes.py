"""REST routes for cross-service tag management."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any

from floci_backend.application.tags_service import TagsService


class TagResourcesRequest(BaseModel):
    resourceArns: List[str]
    tags: Dict[str, str]


class UntagResourcesRequest(BaseModel):
    resourceArns: List[str]
    tagKeys: List[str]


class GetResourcesRequest(BaseModel):
    tagFilters: Optional[List[Dict[str, Any]]] = None
    resourceTypes: Optional[List[str]] = None


def create_tags_router(tags_service: TagsService) -> APIRouter:
    router = APIRouter()

    @router.get("/tags/keys")
    async def get_tag_keys():
        try:
            return await tags_service.get_tag_keys()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/tags/values/{key}")
    async def get_tag_values(key: str):
        try:
            return await tags_service.get_tag_values(key)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/tags/resources/search")
    async def get_resources(req: GetResourcesRequest):
        try:
            return await tags_service.get_resources(
                tag_filters=req.tagFilters,
                resource_types=req.resourceTypes,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/tags/resources/tag")
    async def tag_resources(req: TagResourcesRequest):
        try:
            return await tags_service.tag_resources(req.resourceArns, req.tags)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/tags/resources/untag")
    async def untag_resources(req: UntagResourcesRequest):
        try:
            return await tags_service.untag_resources(req.resourceArns, req.tagKeys)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
