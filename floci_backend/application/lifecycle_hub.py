"""Lifecycle webhooks + interceptores HTTP declarativos (Área 6 — Extensibilidad).

* Webhooks: el emulador dispara eventos de ciclo de vida (ej. ``floci.resource.created``)
  y los reenvía por POST a URLs registradas, para integrarse con notificaciones u
  otros agentes de IA del entorno.
* Interceptores: reglas declarativas que modifican peticiones/respuestas que pasan
  por el proxy de Floci (inyectar cabeceras, forzar status, añadir latencia). Son
  declarativas a propósito (no ejecutan código arbitrario) para mantener el entorno
  local seguro por defecto.

Persiste en ``<state_dir>/lifecycle.json``.
"""
import fnmatch
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx

from floci_backend.config import config


class LifecycleHub:
    def __init__(self):
        self._path = os.path.join(config.state_dir, "lifecycle.json")

    # ----------------------------------------------------------- persistence
    def _load(self) -> Dict[str, Any]:
        try:
            with open(self._path, "r") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"webhooks": [], "interceptors": []}

    def _save(self, data: Dict[str, Any]) -> None:
        os.makedirs(config.state_dir, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)

    # --------------------------------------------------------------- webhooks
    def list_webhooks(self) -> List[Dict[str, Any]]:
        return self._load().get("webhooks", [])

    def register_webhook(self, event: str, url: str, description: str = "") -> Dict[str, Any]:
        data = self._load()
        hook = {
            "id": str(uuid.uuid4()),
            "event": event,
            "url": url,
            "description": description,
            "active": True,
            "createdAt": time.time(),
            "lastDelivery": None,
        }
        data.setdefault("webhooks", []).append(hook)
        self._save(data)
        return hook

    def delete_webhook(self, webhook_id: str) -> bool:
        data = self._load()
        before = len(data.get("webhooks", []))
        data["webhooks"] = [h for h in data.get("webhooks", []) if h["id"] != webhook_id]
        self._save(data)
        return len(data["webhooks"]) < before

    async def emit(self, event: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispara un evento de ciclo de vida hacia todos los webhooks que casen."""
        data = self._load()
        delivered: List[Dict[str, Any]] = []
        body = {"event": event, "payload": payload or {}, "timestamp": time.time()}
        async with httpx.AsyncClient(timeout=5.0) as client:
            for hook in data.get("webhooks", []):
                if not hook.get("active"):
                    continue
                if not fnmatch.fnmatch(event, hook["event"]):
                    continue
                entry = {"webhookId": hook["id"], "url": hook["url"]}
                try:
                    resp = await client.post(hook["url"], json=body)
                    entry["status"] = resp.status_code
                    hook["lastDelivery"] = {"event": event, "status": resp.status_code, "at": time.time()}
                except Exception as e:  # noqa: BLE001
                    entry["error"] = str(e)
                    hook["lastDelivery"] = {"event": event, "error": str(e), "at": time.time()}
                delivered.append(entry)
        self._save(data)
        return {"event": event, "delivered": delivered, "count": len(delivered)}

    # ----------------------------------------------------------- interceptors
    def list_interceptors(self) -> List[Dict[str, Any]]:
        return self._load().get("interceptors", [])

    def register_interceptor(
        self,
        url_pattern: str,
        phase: str = "request",
        action: str = "set_header",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if phase not in ("request", "response"):
            raise ValueError("phase debe ser 'request' o 'response'")
        if action not in ("set_header", "set_status", "delay_ms"):
            raise ValueError("action debe ser 'set_header', 'set_status' o 'delay_ms'")
        data = self._load()
        rule = {
            "id": str(uuid.uuid4()),
            "urlPattern": url_pattern,
            "phase": phase,
            "action": action,
            "params": params or {},
            "active": True,
            "createdAt": time.time(),
        }
        data.setdefault("interceptors", []).append(rule)
        self._save(data)
        return rule

    def delete_interceptor(self, interceptor_id: str) -> bool:
        data = self._load()
        before = len(data.get("interceptors", []))
        data["interceptors"] = [r for r in data.get("interceptors", []) if r["id"] != interceptor_id]
        self._save(data)
        return len(data["interceptors"]) < before

    def matching_interceptors(self, url: str, phase: str) -> List[Dict[str, Any]]:
        out = []
        for rule in self._load().get("interceptors", []):
            if not rule.get("active"):
                continue
            if rule["phase"] != phase:
                continue
            if rule["urlPattern"] in url or fnmatch.fnmatch(url, rule["urlPattern"]):
                out.append(rule)
        return out
