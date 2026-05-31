from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional

from floci_backend.application.lifecycle_hub import LifecycleHub
from floci_backend.application.plugin_registry import PluginRegistry


def create_extensibility_router(
    lifecycle_hub: LifecycleHub, plugin_registry: PluginRegistry
) -> APIRouter:
    router = APIRouter()

    # ----------------------------------------------------------- webhooks
    @router.get("/extensibility/webhooks")
    async def list_webhooks():
        return {"webhooks": lifecycle_hub.list_webhooks()}

    class WebhookRequest(BaseModel):
        event: str
        url: str
        description: str = ""

    @router.post("/extensibility/webhooks")
    async def register_webhook(req: WebhookRequest):
        return lifecycle_hub.register_webhook(req.event, req.url, req.description)

    @router.delete("/extensibility/webhooks/{webhook_id}")
    async def delete_webhook(webhook_id: str):
        if not lifecycle_hub.delete_webhook(webhook_id):
            raise HTTPException(status_code=404, detail="Webhook no encontrado")
        return {"deleted": webhook_id}

    class EmitRequest(BaseModel):
        event: str
        payload: Optional[Dict[str, Any]] = None

    @router.post("/extensibility/webhooks/emit")
    async def emit_event(req: EmitRequest):
        return await lifecycle_hub.emit(req.event, req.payload)

    # ------------------------------------------------------- interceptors
    @router.get("/extensibility/interceptors")
    async def list_interceptors():
        return {"interceptors": lifecycle_hub.list_interceptors()}

    class InterceptorRequest(BaseModel):
        url_pattern: str
        phase: str = "request"
        action: str = "set_header"
        params: Optional[Dict[str, Any]] = None

    @router.post("/extensibility/interceptors")
    async def register_interceptor(req: InterceptorRequest):
        try:
            return lifecycle_hub.register_interceptor(req.url_pattern, req.phase, req.action, req.params)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.delete("/extensibility/interceptors/{interceptor_id}")
    async def delete_interceptor(interceptor_id: str):
        if not lifecycle_hub.delete_interceptor(interceptor_id):
            raise HTTPException(status_code=404, detail="Interceptor no encontrado")
        return {"deleted": interceptor_id}

    # ------------------------------------------------------------ plugins
    @router.get("/extensibility/plugins")
    async def list_plugins():
        return plugin_registry.list_plugins()

    return router
