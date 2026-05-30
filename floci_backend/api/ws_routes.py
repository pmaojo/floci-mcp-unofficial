"""WebSocket endpoint for real-time resource updates."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from floci_backend.application.realtime_service import RealtimeService


def create_ws_router(realtime: RealtimeService) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await realtime.connect(ws)
        try:
            while True:
                data = await ws.receive_text()
                if data == "ping":
                    await ws.send_text("pong")
        except WebSocketDisconnect:
            await realtime.disconnect(ws)
        except Exception:
            await realtime.disconnect(ws)

    return router
