"""Health checks, arquitectura y utilidades generales del entorno."""
import httpx
from floci_backend.config import config
from floci_backend.server import app
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def check_floci_health() -> dict:
        """Verifica si el backend de Floci y el emulador AWS están respondiendo. Devuelve estado de cada componente."""
        backend_ok, backend_details = False, {}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as c:
            try:
                r = await c.get("/health")
                backend_ok = r.status_code == 200
                backend_details = r.json()
            except Exception as e:
                backend_details = {"error": str(e)}

        aws_ok, aws_details = False, {}
        async with httpx.AsyncClient(timeout=5.0) as c:
            try:
                r = await c.get(f"{config.aws_endpoint_url}/_localstack/health")
                aws_ok = r.status_code == 200
                aws_details = r.json()
            except Exception as e:
                aws_details = {"error": str(e)}

        return {
            "backend": {"status": "Online" if backend_ok else "Offline", "details": backend_details},
            "aws_emulator": {"status": "Online" if aws_ok else "Offline", "url": config.aws_endpoint_url, "details": aws_details},
            "overall": "OK" if (backend_ok and aws_ok) else "Degradado",
        }

    @mcp.tool()
    async def list_aws_services() -> dict:
        """Lista el catálogo completo de servicios AWS que Floci puede gestionar (S3, Lambda, SQS, SNS, etc.)."""
        return await backend("GET", "/api/aws-services")

    @mcp.tool()
    async def get_service_resources(service_key: str) -> dict:
        """
        Lee el inventario de recursos de un servicio AWS específico.

        Ejemplos de service_key: 's3', 'lambda', 'sqs', 'sns', 'dynamodb', 'iam', 'rds'.
        """
        return await backend("GET", f"/api/aws-services/{service_key.lower()}/overview")

    @mcp.tool()
    async def get_architecture_diagram() -> dict:
        """
        Devuelve un diagrama con todos los recursos activos del entorno:
        buckets S3, colas SQS, tablas DynamoDB, funciones Lambda, APIs y claves KMS.
        """
        return await backend("GET", "/api/studio/architecture")

    @mcp.tool()
    async def get_cost_forecast() -> dict:
        """Estima el coste mensual del entorno actual basado en los recursos desplegados."""
        return await backend("GET", "/api/diagnostics/cost-forecast")

    @mcp.tool()
    async def get_network_topology() -> dict:
        """Devuelve el mapa de red Docker local de Floci con contenedores, redes y puertos expuestos."""
        return await backend("GET", "/api/extensions/network-topology")
