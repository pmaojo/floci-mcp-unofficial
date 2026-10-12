"""Herramientas de desarrollo: IaC, seed data, proxy HTTP, JWT y tests."""
import asyncio
import glob
import os
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def export_to_terraform(format: str = "terraform") -> dict:
        """
        Generates infrastructure code from the resources currently in the emulator.

        format: 'terraform' (default) or 'cdk'.
        Covers S3, SQS, DynamoDB, Lambda and KMS.
        """
        return await backend("GET", f"/api/extensions/export-iac?format={format}")

    @mcp.tool()
    async def export_recipes_to_terraform() -> dict:
        """
        Generates Terraform for the marketplace recipes that are RUNNING.

        Each installed recipe maps to its managed AWS equivalent (RDS, ElastiCache, MSK,
        OpenSearch, Cognito, ...). Passwords are emitted as Terraform variables
        (sensitive = true) so they never appear in plain text.

        Use it after validating your stack locally to get production infrastructure ready
        for 'terraform apply'.
        """
        return await backend("GET", "/api/extensions/export-iac-recipes")

    @mcp.tool()
    async def run_local_aws_cmd(command: str) -> dict:
        """
        Runs an aws-cli command directly against the Floci emulator.

        Escape hatch for operations the other tools do not cover.
        Write the command without the 'aws' prefix, e.g. 's3 ls' or 'sqs list-queues'.
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
        Injects synthetic data (Faker) into DynamoDB, S3 or PostgreSQL.

        target: 'dynamodb', 's3' or 'postgres'.
        target_name: table, bucket or database name.
        connection_string: only for target='postgres' (e.g. 'postgresql://user:pass@localhost:5432/db').
        custom_schema: example JSON schema that guides the data generation.
        """
        return await backend("POST", "/api/extensions/seed-data", json_data={
            "target": target,
            "target_name": target_name,
            "connection_string": connection_string,
            "custom_schema": custom_schema,
        })

    @mcp.tool()
    async def get_resource_relations(resource_id: str, resource_type: str) -> dict:
        """
        Returns the dependency graph of an AWS resource.

        Useful for questions such as "which lambdas consume this SQS queue?" or
        "where does this S3 bucket point to?".

        resource_id: resource name (e.g. 'my-lambda') or its ARN.
        resource_type: Lambda, SQS, SNS, S3, DynamoDB or EventBridge.
        """
        import urllib.parse
        return await backend("GET", f"/api/studio/resource-explorer?resource_id={urllib.parse.quote(resource_id)}&resource_type={urllib.parse.quote(resource_type)}")

    @mcp.tool()
    async def proxy_http_request(
        url: str,
        method: str = "GET",
        headers: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """
        Sends an HTTP request from the Floci backend, avoiding CORS restrictions.

        Useful to test local APIs, webhooks and internal endpoints.
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
        Generates a signed JWT for authentication in local tests.

        claims: token payload (sub, email, roles, exp, ...).
        Example: generate_jwt_token({'sub': 'user-1', 'email': 'dev@floci.io', 'roles': ['admin']})
        """
        return await backend("POST", "/api/studio/auth/generate-token", json_data={
            "claims": claims,
            "secret": secret,
            "algorithm": algorithm,
        })

    @mcp.tool()
    async def run_ui_tests(test_file: str | None = None) -> dict:
        """
        Runs the Playwright tests of the Floci Studio frontend.

        If test_file is given only that test runs.
        Returns stdout, stderr and screenshot paths on failure.
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
