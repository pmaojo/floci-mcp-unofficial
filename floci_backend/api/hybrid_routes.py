from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from floci_backend.application.hybrid_service import HybridService


def create_hybrid_router(hybrid_service: HybridService) -> APIRouter:
    router = APIRouter()

    class CloudSeedRequest(BaseModel):
        source_table: str
        target_table: Optional[str] = None
        limit: int = 25
        anonymize_fields: Optional[List[str]] = None
        region: Optional[str] = None
        aws_access_key_id: Optional[str] = None
        aws_secret_access_key: Optional[str] = None
        aws_session_token: Optional[str] = None

    @router.post("/hybrid/seed-from-cloud")
    async def seed_from_cloud(req: CloudSeedRequest):
        try:
            return await hybrid_service.seed_from_cloud_dynamodb(
                source_table=req.source_table,
                target_table=req.target_table,
                limit=req.limit,
                anonymize_fields=req.anonymize_fields,
                region=req.region,
                aws_access_key_id=req.aws_access_key_id,
                aws_secret_access_key=req.aws_secret_access_key,
                aws_session_token=req.aws_session_token,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class CloudProxyRequest(BaseModel):
        source_queue_url: str
        target_type: str
        target: str
        max_messages: int = 10
        delete_after: bool = True
        region: Optional[str] = None
        aws_access_key_id: Optional[str] = None
        aws_secret_access_key: Optional[str] = None
        aws_session_token: Optional[str] = None

    @router.post("/hybrid/cloud-proxy/sqs")
    async def proxy_cloud_sqs(req: CloudProxyRequest):
        try:
            return await hybrid_service.proxy_cloud_sqs(
                source_queue_url=req.source_queue_url,
                target_type=req.target_type,
                target=req.target,
                max_messages=req.max_messages,
                delete_after=req.delete_after,
                region=req.region,
                aws_access_key_id=req.aws_access_key_id,
                aws_secret_access_key=req.aws_secret_access_key,
                aws_session_token=req.aws_session_token,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class TunnelRequest(BaseModel):
        port: int = 4566

    @router.get("/hybrid/tunnels")
    async def list_tunnels():
        return {"tunnels": hybrid_service.list_tunnels()}

    @router.post("/hybrid/tunnels")
    async def start_tunnel(req: TunnelRequest):
        try:
            return await hybrid_service.start_tunnel(req.port)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/hybrid/tunnels/{pid}")
    async def stop_tunnel(pid: str):
        return hybrid_service.stop_tunnel(pid)

    return router
