"""Herramientas Lambda: funciones serverless completas."""
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def get_lambda_runtimes() -> dict:
        """Lista los runtimes disponibles en Floci (Node.js, Python, Go, Java) y los templates de código por defecto."""
        return await backend("GET", "/api/lambda/capabilities")

    @mcp.tool()
    async def list_lambda_functions() -> dict:
        """Lista todas las funciones Lambda desplegadas en el entorno con su configuración."""
        return await backend("GET", "/api/lambda/functions")

    @mcp.tool()
    async def create_lambda_function(
        function_name: str,
        runtime: str,
        handler: str,
        code: dict,
        description: str = "",
        timeout: int = 30,
        memory_size: int = 128,
    ) -> dict:
        """
        Crea una nueva función Lambda.

        runtime: 'nodejs18.x', 'python3.9', 'go1.x', 'java11', 'provided.al2'.
        handler: punto de entrada, ej. 'index.handler' (Node) o 'main.handler' (Python).
        code admite tres modos:
          - {'mode': 'template'} — usa el template por defecto del runtime
          - {'mode': 'inline', 'fileName': 'index.js', 'source': '...'} — código directo
          - {'mode': 'zipBase64', 'zipBase64': '...'} — ZIP en base64
        """
        return await backend("POST", "/api/lambda/functions", json_data={
            "functionName": function_name,
            "runtime": runtime,
            "handler": handler,
            "code": code,
            "description": description,
            "timeout": timeout,
            "memorySize": memory_size,
        })

    @mcp.tool()
    async def update_lambda_code(function_name: str, runtime: str, code: dict) -> dict:
        """
        Actualiza el código fuente de una función Lambda existente.

        Mismos formatos de code que create_lambda_function.
        """
        return await backend("PUT", f"/api/lambda/functions/{function_name}/code", json_data={
            "runtime": runtime,
            "code": code,
        })

    @mcp.tool()
    async def update_lambda_config(
        function_name: str,
        handler: str | None = None,
        timeout: int | None = None,
        memory_size: int | None = None,
        description: str | None = None,
    ) -> dict:
        """Actualiza la configuración de una función Lambda: handler, timeout, memoria o descripción."""
        payload = {k: v for k, v in {
            "handler": handler,
            "timeout": timeout,
            "memorySize": memory_size,
            "description": description,
        }.items() if v is not None}
        return await backend("PUT", f"/api/lambda/functions/{function_name}/configuration", json_data=payload)

    @mcp.tool()
    async def invoke_lambda(
        function_name: str,
        payload: dict | None = None,
        async_invocation: bool = False,
    ) -> dict:
        """
        Invoca una función Lambda y devuelve su respuesta.

        async_invocation=true usa invocación Event (fire-and-forget, sin esperar respuesta).
        Por defecto usa RequestResponse (síncrono, devuelve el resultado).
        """
        return await backend("POST", f"/api/lambda/functions/{function_name}/invoke", json_data={
            "payload": payload or {},
            "async": async_invocation,
        })

    @mcp.tool()
    async def get_lambda_logs(function_name: str) -> dict:
        """Obtiene los logs de CloudWatch de una función Lambda."""
        return await backend("GET", f"/api/lambda/functions/{function_name}/logs")

    @mcp.tool()
    async def delete_lambda(function_name: str) -> dict:
        """Elimina una función Lambda del entorno."""
        return await backend("DELETE", f"/api/lambda/functions/{function_name}")
