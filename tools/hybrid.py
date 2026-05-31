"""Desarrollo híbrido: cloud proxying, seeding desde la nube y túneles (Área 5)."""
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def seed_from_cloud_dynamodb(
        source_table: str,
        target_table: str | None = None,
        limit: int = 25,
        anonymize_fields: list[str] | None = None,
        region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> dict:
        """
        Extrae un subconjunto de una tabla DynamoDB REAL, lo anonimiza e inyecta
        en la tabla local del emulador.

        Requiere credenciales AWS reales (parámetros o el entorno del backend).
        Si anonymize_fields es None se anonimizan automáticamente campos sensibles
        (email, name, phone, address); pásalo para limitar a campos concretos.
        """
        return await backend("POST", "/api/hybrid/seed-from-cloud", json_data={
            "source_table": source_table, "target_table": target_table,
            "limit": limit, "anonymize_fields": anonymize_fields,
            "region": region, "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
        })

    @mcp.tool()
    async def proxy_cloud_sqs_to_local(
        source_queue_url: str,
        target_type: str,
        target: str,
        max_messages: int = 10,
        delete_after: bool = True,
        region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> dict:
        """
        Drena mensajes de una cola SQS REAL (ej. staging) y los reenvía a un recurso
        local (Lambda/SQS/SNS) para un bucle de feedback inmediato.

        target_type: 'lambda', 'sqs' o 'sns'. Drenaje puntual de hasta max_messages.
        """
        return await backend("POST", "/api/hybrid/cloud-proxy/sqs", json_data={
            "source_queue_url": source_queue_url, "target_type": target_type,
            "target": target, "max_messages": max_messages, "delete_after": delete_after,
            "region": region, "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
        })

    @mcp.tool()
    async def start_reverse_tunnel(port: int = 4566) -> dict:
        """
        Expone un puerto local a internet con una URL temporal (estilo ngrok).

        Útil para probar webhooks de terceros (Stripe, GitHub) contra un API Gateway
        local. Requiere 'cloudflared' o 'ngrok' instalado en el host.
        """
        return await backend("POST", "/api/hybrid/tunnels", json_data={"port": port})

    @mcp.tool()
    async def list_reverse_tunnels() -> dict:
        """Lista los túneles inversos activos iniciados por Floci."""
        return await backend("GET", "/api/hybrid/tunnels")

    @mcp.tool()
    async def stop_reverse_tunnel(pid: str) -> dict:
        """Detiene un túnel inverso por su PID."""
        return await backend("DELETE", f"/api/hybrid/tunnels/{pid}")
