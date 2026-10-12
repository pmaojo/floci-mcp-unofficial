"""Sending HTTP requests to the Azure, GCP and OCI runtimes of Floci."""
import os
from typing import Any

import httpx

AZURE_API_VERSION = "2021-12-02"
_ENDPOINTS = {
    "aws": ("AWS_ENDPOINT_URL", "http://localhost:4566"),
    "azure": ("FLOCI_AZURE_ENDPOINT", "http://localhost:4577"),
    "gcp": ("FLOCI_GCP_ENDPOINT", "http://localhost:4588"),
    "oci": ("FLOCI_OCI_ENDPOINT", "http://localhost:4599"),
}


class HttpxRestTransport:
    """Implements ports.RestTransport with httpx."""

    def __init__(self, env: dict | None = None, timeout: float = 15) -> None:
        self._env = env if env is not None else os.environ
        self._timeout = timeout

    def endpoint(self, cloud: str) -> str:
        """The base URL of a cloud's runtime."""
        name, default = _ENDPOINTS[cloud]
        return self._env.get(name, default).rstrip("/")

    def send(self, cloud: str, method: str, path: str, request: dict) -> dict:
        """Send one request; {"status", "body"}, or {"error": "Unreachable", ...}."""
        headers = {str(k): str(v) for k, v in (request.get("headers") or {}).items()}
        if cloud == "azure":
            headers.setdefault("x-ms-version", AZURE_API_VERSION)
            headers.setdefault("authorization", "Bearer floci-mcp")
        try:
            with httpx.Client(base_url=self.endpoint(cloud), timeout=self._timeout) as client:
                response = client.request(method, path, params=request.get("query"), json=request.get("json"),
                                          content=request.get("body"), headers=headers)
        except httpx.HTTPError as exc:
            return {"error": "Unreachable", "message": f"Cannot reach the {cloud} runtime: {exc}"}
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return {"status": response.status_code, "body": body}
