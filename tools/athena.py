"""Herramientas Athena: consultas SQL y catálogo Glue."""
import asyncio
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def list_glue_databases() -> dict:
        """Lista las bases de datos y tablas del catálogo de datos de AWS Glue (usado por Athena)."""
        return await backend("GET", "/api/athena/catalog")

    @mcp.tool()
    async def run_athena_query(
        sql: str,
        database: str = "default",
        workgroup: str = "primary",
        timeout_seconds: int = 30,
    ) -> dict:
        """
        Ejecuta una consulta SQL en Athena y espera el resultado completo.

        Hace polling hasta que la consulta termina o se alcanza timeout_seconds.
        Devuelve las filas directamente, sin necesidad de llamadas adicionales.
        """
        start = await backend("POST", "/api/athena/query", json_data={
            "query": sql,
            "database": database,
            "workGroup": workgroup,
        })
        exec_id = start.get("executionId")
        if not exec_id:
            return start

        for _ in range(timeout_seconds):
            await asyncio.sleep(1)
            status_resp = await backend("GET", f"/api/athena/query/{exec_id}")
            status = status_resp.get("status")
            if status == "SUCCEEDED":
                return await backend("GET", f"/api/athena/query/{exec_id}/results")
            if status in ("FAILED", "CANCELLED"):
                return {"status": status, "reason": status_resp.get("stateChangeReason"), "execution_id": exec_id}

        return {"status": "TIMEOUT", "execution_id": exec_id, "message": f"Consulta no terminó en {timeout_seconds}s"}

    @mcp.tool()
    async def get_athena_query_history() -> dict:
        """Obtiene el historial de consultas Athena ejecutadas en la sesión actual."""
        return await backend("GET", "/api/athena/history")
