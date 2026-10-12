"""Multi-cloud tools: Azure (Floci-AZ), GCP (Floci-GCP) and OCI (Floci-OCI).

AWS keeps its per-service modules next to this one. The other three runtimes
speak their provider's own REST contract, so these tools call it directly and
do not go through the Studio backend.
"""
import os
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import httpx

AZURE_API_VERSION = "2021-12-02"
KEYVAULT_API_VERSION = "7.4"
DEFAULT_TENANCY = "ocid1.tenancy.oc1..flocilocaltenancy0000000000000000000000000000000000000000"

# Health paths differ per runtime: GCP and OCI do not answer /_floci/health.
HEALTH_PATHS = {
    "aws": "/_floci/health",
    "azure": "/_floci/health",
    "gcp": "/_floci-gcp/health",
    "oci": "/_floci-oci/health",
}


def endpoint(cloud: str) -> str:
    env = {
        "aws": ("AWS_ENDPOINT_URL", "http://localhost:4566"),
        "azure": ("FLOCI_AZURE_ENDPOINT", "http://localhost:4577"),
        "gcp": ("FLOCI_GCP_ENDPOINT", "http://localhost:4588"),
        "oci": ("FLOCI_OCI_ENDPOINT", "http://localhost:4599"),
    }[cloud]
    return os.environ.get(env[0], env[1]).rstrip("/")


def azure_account() -> str:
    return os.environ.get("FLOCI_AZURE_ACCOUNT_NAME", "devstoreaccount1")


def gcp_project() -> str:
    return os.environ.get("FLOCI_GCP_PROJECT", "floci-local")


def oci_tenancy() -> str:
    return os.environ.get("FLOCI_OCI_TENANCY_ID", DEFAULT_TENANCY)


def _q(value: str) -> str:
    return quote(value, safe="")


class CloudRuntimeError(Exception):
    """A runtime answered with an error, or could not be reached."""


async def _request(
    cloud: str,
    method: str,
    path: str,
    *,
    json: Any = None,
    content: bytes | str | None = None,
    headers: dict[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.Response:
    base = endpoint(cloud)
    send_headers = dict(headers or {})
    if cloud == "azure":
        send_headers.setdefault("x-ms-version", AZURE_API_VERSION)
    try:
        async with httpx.AsyncClient(base_url=base, timeout=15, transport=transport) as client:
            response = await client.request(method, path, json=json, content=content, headers=send_headers)
    except httpx.HTTPError as exc:
        raise CloudRuntimeError(f"Cannot reach the {cloud} runtime at {base}: {exc}") from exc
    if response.status_code >= 400:
        detail = response.text.strip()[:500]
        raise CloudRuntimeError(f"{cloud} runtime returned HTTP {response.status_code} for {method} {path}: {detail}")
    return response


def _xml_names(body: str, element: str) -> list[str]:
    root = ET.fromstring(body)
    return [node.text or "" for node in root.iter(element) if node.text]


async def runtime_status(cloud: str, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    base = endpoint(cloud)
    try:
        async with httpx.AsyncClient(base_url=base, timeout=5, transport=transport) as client:
            response = await client.get(HEALTH_PATHS[cloud])
    except httpx.HTTPError:
        return {"cloud": cloud, "endpoint": base, "status": "unreachable"}
    status = "online" if response.status_code < 500 else "unhealthy"
    return {"cloud": cloud, "endpoint": base, "status": status, "httpStatus": response.status_code}


def register(mcp):

    @mcp.tool()
    async def list_clouds() -> dict:
        """
        Reports which Floci runtimes are reachable: aws, azure, gcp and oci.

        Call it first to know which cloud-specific tools can work. Endpoints come from
        AWS_ENDPOINT_URL, FLOCI_AZURE_ENDPOINT, FLOCI_GCP_ENDPOINT and FLOCI_OCI_ENDPOINT.
        """
        return {"clouds": [await runtime_status(cloud) for cloud in ("aws", "azure", "gcp", "oci")]}

    # ------------------------------------------------------------------ GCP
    @mcp.tool()
    async def gcp_list_buckets() -> dict:
        """Lists Cloud Storage buckets in the configured GCP project (Floci-GCP)."""
        response = await _request("gcp", "GET", f"/storage/v1/b?project={_q(gcp_project())}")
        items = response.json().get("items", [])
        return {"project": gcp_project(), "buckets": [item.get("name") for item in items]}

    @mcp.tool()
    async def gcp_create_bucket(name: str) -> dict:
        """Creates a Cloud Storage bucket in the configured GCP project (Floci-GCP)."""
        response = await _request("gcp", "POST", f"/storage/v1/b?project={_q(gcp_project())}", json={"name": name})
        return response.json()

    @mcp.tool()
    async def gcp_list_objects(bucket: str, prefix: str = "") -> dict:
        """Lists the objects of a Cloud Storage bucket, optionally under a prefix."""
        query = f"?prefix={_q(prefix)}" if prefix else ""
        response = await _request("gcp", "GET", f"/storage/v1/b/{_q(bucket)}/o{query}")
        body = response.json()
        return {"bucket": bucket, "objects": [item.get("name") for item in body.get("items", [])]}

    @mcp.tool()
    async def gcp_list_topics() -> dict:
        """Lists Pub/Sub topics in the configured GCP project."""
        response = await _request("gcp", "GET", f"/v1/projects/{_q(gcp_project())}/topics")
        return {"topics": [topic.get("name") for topic in response.json().get("topics", [])]}

    @mcp.tool()
    async def gcp_create_topic(name: str) -> dict:
        """Creates a Pub/Sub topic (Floci-GCP uses PUT, as the real API does)."""
        response = await _request("gcp", "PUT", f"/v1/projects/{_q(gcp_project())}/topics/{_q(name)}")
        return response.json()

    @mcp.tool()
    async def gcp_list_secrets() -> dict:
        """Lists Secret Manager secrets in the configured GCP project (names only, never values)."""
        response = await _request("gcp", "GET", f"/v1/projects/{_q(gcp_project())}/secrets")
        return {"secrets": [secret.get("name") for secret in response.json().get("secrets", [])]}

    # ---------------------------------------------------------------- Azure
    @mcp.tool()
    async def azure_list_containers() -> dict:
        """Lists Blob Storage containers of the Floci-AZ storage account."""
        response = await _request("azure", "GET", f"/{_q(azure_account())}?comp=list")
        return {"account": azure_account(), "containers": _xml_names(response.text, "Name")}

    @mcp.tool()
    async def azure_create_container(name: str) -> dict:
        """Creates a Blob Storage container."""
        await _request("azure", "PUT", f"/{_q(azure_account())}/{_q(name)}?restype=container")
        return {"account": azure_account(), "container": name, "created": True}

    @mcp.tool()
    async def azure_list_blobs(container: str, prefix: str = "") -> dict:
        """Lists the blobs of a container, optionally under a prefix."""
        query = "restype=container&comp=list" + (f"&prefix={_q(prefix)}" if prefix else "")
        response = await _request("azure", "GET", f"/{_q(azure_account())}/{_q(container)}?{query}")
        return {"container": container, "blobs": _xml_names(response.text, "Name")}

    @mcp.tool()
    async def azure_list_queues() -> dict:
        """Lists Queue Storage queues of the Floci-AZ storage account."""
        response = await _request("azure", "GET", f"/{_q(azure_account())}-queue?comp=list")
        return {"account": azure_account(), "queues": _xml_names(response.text, "Name")}

    @mcp.tool()
    async def azure_create_queue(name: str) -> dict:
        """Creates a Queue Storage queue."""
        await _request("azure", "PUT", f"/{_q(azure_account())}-queue/{_q(name)}")
        return {"account": azure_account(), "queue": name, "created": True}

    @mcp.tool()
    async def azure_list_secrets() -> dict:
        """Lists Key Vault secret identifiers (names only, never values)."""
        response = await _request(
            "azure",
            "GET",
            f"/{_q(azure_account())}-keyvault/secrets?api-version={KEYVAULT_API_VERSION}",
            headers={"authorization": "Bearer floci-mcp"},
        )
        return {"secrets": [item.get("id") for item in response.json().get("value", [])]}

    # ------------------------------------------------------------------ OCI
    async def _oci_namespace() -> str:
        response = await _request("oci", "GET", "/n/")
        return response.json()

    @mcp.tool()
    async def oci_list_buckets() -> dict:
        """Lists Object Storage buckets in the default compartment (Floci-OCI)."""
        namespace = await _oci_namespace()
        response = await _request("oci", "GET", f"/n/{_q(namespace)}/b?compartmentId={_q(oci_tenancy())}")
        return {"namespace": namespace, "buckets": [bucket.get("name") for bucket in response.json()]}

    @mcp.tool()
    async def oci_create_bucket(name: str) -> dict:
        """Creates an Object Storage bucket in the default compartment."""
        namespace = await _oci_namespace()
        response = await _request(
            "oci", "POST", f"/n/{_q(namespace)}/b", json={"name": name, "compartmentId": oci_tenancy()}
        )
        return response.json()

    @mcp.tool()
    async def oci_list_objects(bucket: str, prefix: str = "") -> dict:
        """Lists the objects of an Object Storage bucket, optionally under a prefix."""
        namespace = await _oci_namespace()
        query = f"?prefix={_q(prefix)}" if prefix else ""
        response = await _request("oci", "GET", f"/n/{_q(namespace)}/b/{_q(bucket)}/o{query}")
        return {"bucket": bucket, "objects": [item.get("name") for item in response.json().get("objects", [])]}
