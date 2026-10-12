"""Herramientas Lambda: funciones serverless completas."""
from floci_tools._client import backend


def register(mcp):

    @mcp.tool()
    async def get_lambda_runtimes() -> dict:
        """Lists the Lambda runtimes available in Floci (Node.js, Python, Go, Java) and their default code templates."""
        return await backend("GET", "/api/lambda/capabilities")

    @mcp.tool()
    async def list_lambda_functions() -> dict:
        """Lists all Lambda functions deployed in the environment with their configuration."""
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
        Creates a Lambda function.

        runtime: 'nodejs18.x', 'python3.9', 'go1.x', 'java11', 'provided.al2'.
        handler: entry point, e.g. 'index.handler' (Node) or 'main.handler' (Python).
        code takes one of three modes:
          - {'mode': 'template'}: the default template of the runtime
          - {'mode': 'inline', 'fileName': 'index.js', 'source': '...'}: source code
          - {'mode': 'zipBase64', 'zipBase64': '...'}: a base64 ZIP
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
        Updates the source code of an existing Lambda function.

        code uses the same formats as create_lambda_function.
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
        """Updates the configuration of a Lambda function: handler, timeout, memory or description."""
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
        Invokes a Lambda function and returns its response.

        async_invocation=true uses the Event invocation type (fire and forget, no response).
        The default is RequestResponse (synchronous, returns the result).
        """
        return await backend("POST", f"/api/lambda/functions/{function_name}/invoke", json_data={
            "payload": payload or {},
            "async": async_invocation,
        })

    @mcp.tool()
    async def get_lambda_logs(function_name: str) -> dict:
        """Gets the CloudWatch logs of a Lambda function."""
        return await backend("GET", f"/api/lambda/functions/{function_name}/logs")

    @mcp.tool()
    async def delete_lambda(function_name: str) -> dict:
        """Deletes a Lambda function from the environment."""
        return await backend("DELETE", f"/api/lambda/functions/{function_name}")
