"""Herramientas de desarrollo: IaC, seed data, proxy HTTP, JWT y tests."""
import asyncio
import glob
import os
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def export_to_terraform(format: str = "terraform") -> dict:
        """
        Genera código de infraestructura a partir de los recursos actuales del emulador.

        format: 'terraform' (por defecto) o 'cdk'.
        Cubre S3, SQS, DynamoDB, Lambda y KMS.
        """
        return await backend("GET", f"/api/extensions/export-iac?format={format}")

    @mcp.tool()
    async def run_local_aws_cmd(command: str) -> dict:
        """
        Ejecuta un comando aws-cli directamente contra el emulador de Floci.

        Escape hatch para operaciones no cubiertas por otras herramientas.
        Escribe el comando sin el prefijo 'aws', ej: 's3 ls' o 'sqs list-queues'.
        """
        return await backend("POST", "/api/extensions/run-aws-cmd", json_data={"command": command})

    @mcp.tool()
    async def seed_mock_data(
        target: str,
        target_name: str,
        connection_string: str | None = None,
        custom_schema: dict | None = None,
    ) -> dict:
        """
        Inyecta datos sintéticos (Faker) en DynamoDB, S3 o PostgreSQL.

        target: 'dynamodb', 's3' o 'postgres'.
        target_name: nombre de la tabla, bucket o base de datos.
        connection_string: solo para target='postgres' (ej. 'postgresql://user:pass@localhost:5432/db').
        custom_schema: esquema JSON de ejemplo para guiar la generación de datos.
        """
        return await backend("POST", "/api/extensions/seed-data", json_data={
            "target": target,
            "target_name": target_name,
            "connection_string": connection_string,
            "custom_schema": custom_schema,
        })

    @mcp.tool()
    async def proxy_http_request(
        url: str,
        method: str = "GET",
        headers: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """
        Envía una petición HTTP desde el backend de Floci, evitando restricciones CORS.

        Útil para testear APIs locales, webhooks y endpoints internos.
        """
        return await backend("POST", "/api/studio/client/proxy", json_data={
            "url": url,
            "method": method,
            "headers": headers,
            "body": body,
        })

    @mcp.tool()
    async def generate_jwt_token(
        claims: dict,
        secret: str = "local-secret-key-123",
        algorithm: str = "HS256",
    ) -> dict:
        """
        Genera un JWT firmado para autenticación en tests locales.

        claims: payload del token (sub, email, roles, exp, etc.).
        Ejemplo: generate_jwt_token({'sub': 'user-1', 'email': 'dev@floci.io', 'roles': ['admin']})
        """
        return await backend("POST", "/api/studio/auth/generate-token", json_data={
            "claims": claims,
            "secret": secret,
            "algorithm": algorithm,
        })

    @mcp.tool()
    async def run_ui_tests(test_file: str | None = None) -> dict:
        """
        Ejecuta los tests de Playwright del frontend.

        Si se especifica test_file, ejecuta solo ese test.
        Devuelve stdout, stderr y rutas a capturas de pantalla en caso de fallo.
        """
        cmd = ["npx", "playwright", "test"]
        if test_file:
            cmd.append(test_file)
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode()
        errors = stderr.decode()
        screenshots: list[str] = []
        if process.returncode != 0:
            screenshots = glob.glob(os.path.join(os.path.abspath("test-results"), "**", "*.png"), recursive=True)
        return {
            "exit_code": process.returncode,
            "stdout": output,
            "stderr": errors,
            "screenshots": screenshots,
        }
