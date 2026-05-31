from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from floci_backend.application.dlq_service import DlqService
from floci_backend.application.flight_recorder import FlightRecorder
from floci_backend.application.service_graph import ServiceGraph


def create_observability_router(flight_recorder: FlightRecorder) -> APIRouter:
    router = APIRouter()

    # ------------------------------------------------------------------- DLQ
    @router.get("/observability/dlq")
    async def list_dlqs():
        try:
            return DlqService().list_dead_letter_queues()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/observability/dlq/messages")
    async def inspect_dlq(dlq_url: str, max_messages: int = 10):
        try:
            return DlqService().inspect_messages(dlq_url, max_messages)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class RedriveRequest(BaseModel):
        dlq_url: str
        source_url: str
        max_messages: int = 10

    @router.post("/observability/dlq/redrive")
    async def redrive(req: RedriveRequest):
        try:
            return DlqService().redrive(req.dlq_url, req.source_url, req.max_messages)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # --------------------------------------------------------- Service graph
    @router.get("/observability/service-graph")
    async def service_graph():
        try:
            return ServiceGraph().build()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------- Flight recorder
    class CaptureRequest(BaseModel):
        target_type: str
        target: str
        payload: Any
        source: Optional[str] = None
        label: Optional[str] = None

    @router.get("/observability/flight-recorder")
    async def list_events():
        return flight_recorder.list_events()

    @router.post("/observability/flight-recorder")
    async def capture_event(req: CaptureRequest):
        try:
            return flight_recorder.capture(req.target_type, req.target, req.payload, req.source, req.label)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    class PayloadUpdate(BaseModel):
        payload: Any

    @router.put("/observability/flight-recorder/{event_id}")
    async def update_event(event_id: str, req: PayloadUpdate):
        try:
            return flight_recorder.update_payload(event_id, req.payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="Evento no encontrado")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/observability/flight-recorder/{event_id}/replay")
    async def replay_event(event_id: str):
        try:
            return flight_recorder.replay(event_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Evento no encontrado")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/observability/flight-recorder/{event_id}")
    async def discard_event(event_id: str):
        try:
            return flight_recorder.discard(event_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Evento no encontrado")

    return router
