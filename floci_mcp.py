import asyncio
import json
import os
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server.stdio import stdio_server

server = Server("floci-mcp")

# Ya no necesitamos configurar un SIDECAR_URL externo,
# utilizaremos httpx con la app FastAPI directamente en memoria.
from floci_backend.server import app

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Expone el catalogo de herramientas disponibles para el Agente."""
    return [
        types.Tool(
            name="check_floci_health",
            description="Verifica si el backend local de Floci (servidor FastAPI unificado) y el emulador de AWS (Localstack) están respondiendo correctamente.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="list_aws_services",
            description="Obtiene el catalogo completo de servicios de AWS emulados que el backend de Floci puede administrar y visualizar.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="get_service_resources",
            description="Lee el inventario de recursos emulados disponibles para un servicio de AWS en particular (ej. lambdas, buckets s3, topics sns).",
            inputSchema={
                "type": "object",
                "properties": {
                    "serviceKey": {
                        "type": "string",
                        "description": "El identificador del servicio AWS (ej. 's3', 'lambda', 'dynamodb')"
                    }
                },
                "required": ["serviceKey"]
            }
        ),
        types.Tool(
            name="run_kms_diagnostic",
            description="Ejecuta un test de diagnostico de cifrado/descifrado round-trip usando AWS KMS real en Floci.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="list_marketplace_recipes",
            description="Obtiene el catalogo completo de recetas de software locales disponibles en el Marketplace (ej. postgres, redis, rabbitmq, keycloak) junto con sus variables de entorno admitidas.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="get_marketplace_installations",
            description="Obtiene la lista de instalaciones activas en el Marketplace, mostrando el estado actual de Docker de cada servicio (RUNNING, FAILED, INSTALLING, etc.), variables configuradas y marcas de tiempo.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="get_marketplace_logs",
            description="Obtiene la traza en vivo de logs generados por Docker Compose para una receta especifica del Marketplace, util para diagnosticar fallos en instalaciones.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipeId": {
                        "type": "string",
                        "description": "El identificador unico de la receta (ej. 'redis', 'postgres', 'rabbitmq', 'keycloak')"
                    }
                },
                "required": ["recipeId"]
            }
        ),
        types.Tool(
            name="deploy_marketplace_app",
            description="Instala y levanta una receta del Marketplace de software local (ej. 'redis', 'postgres', 'rabbitmq', 'keycloak') en Docker local.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipeId": {
                        "type": "string",
                        "description": "ID de la receta a instalar (ej. 'redis', 'postgres', 'rabbitmq')"
                    },
                    "vars": {
                        "type": "object",
                        "description": "Variables de configuracion opcionales de la receta (ej. contrasenas, puertos de mapeo)"
                    }
                },
                "required": ["recipeId"]
            }
        ),
        types.Tool(
            name="teardown_marketplace_app",
            description="Detiene y desinstala una receta instalada del Marketplace de software local usando su ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipeId": {
                        "type": "string",
                        "description": "ID de la receta a desinstalar (ej. 'redis')"
                    }
                },
                "required": ["recipeId"]
            }
        ),
        types.Tool(
            name="export_to_terraform",
            description="Genera codigo Terraform automaticamente a partir de los recursos actuales en el emulador local.",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "description": "Formato de exportacion, ej. 'terraform' o 'cdk'. Por defecto 'terraform'"
                    }
                }
            }
        ),
        types.Tool(
            name="run_local_aws_cmd",
            description="Ejecuta comandos estandar de aws-cli en el entorno local (apuntando al emulador de Floci).",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "El comando de AWS CLI a ejecutar (ej. 's3 ls' o 'aws s3 mb s3://test')"
                    }
                },
                "required": ["command"]
            }
        ),
        types.Tool(
            name="seed_mock_data",
            description="Inyecta datos sinteticos en bases de datos locales o S3.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "El destino de los datos (ej. 'postgres', 'dynamodb', 's3')"
                    },
                    "target_name": {
                        "type": "string",
                        "description": "El nombre de la tabla, base de datos o bucket destino"
                    },
                    "connection_string": {
                        "type": "string",
                        "description": "Cadena de conexion (requerida para postgres, ej. 'postgresql://user:pass@host:5432/db')"
                    },
                    "custom_schema": {
                        "type": "object",
                        "description": "Esquema JSON de ejemplo para generar los datos"
                    }
                },
                "required": ["target", "target_name"]
            }
        ),
        types.Tool(
            name="get_network_topology",
            description="Devuelve un mapa en formato Mermaid de la topologia de red Docker local de Floci y sus puertos.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="run_ui_tests",
            description="Ejecuta tests de Playwright para el frontend y devuelve la ruta de las capturas de pantalla en caso de fallo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_file": {
                        "type": "string",
                        "description": "Ruta o nombre del archivo de test especifico a ejecutar"
                    }
                }
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str,
    arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Ejecuta una herramienta y devuelve la respuesta en formato de contenido MCP."""
    
    async def call_backend(method: str, path: str, json_data: dict = None) -> str:
        # Usamos httpx.AsyncClient pero atado directamente a la aplicacion FastAPI 'app'
        # Esto elimina la necesidad de un puerto de red local y funciona de maravilla.

        headers = {}
        # Forward token if available from environment to satisfy token_middleware
        token = os.environ.get("SIDECAR_TOKEN")
        if token:
            headers["x-floci-sidecar-token"] = token

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            try:
                if method.upper() == "GET":
                    resp = await client.get(path, headers=headers)
                elif method.upper() == "POST":
                    resp = await client.post(path, headers=headers, json=json_data)
                elif method.upper() == "DELETE":
                    resp = await client.delete(path, headers=headers)
                else:
                    return json.dumps({"ok": False, "error": f"Metodo HTTP {method} no soportado"})
                
                if resp.status_code >= 400:
                    return json.dumps({
                        "ok": False, 
                        "statusCode": resp.status_code, 
                        "error": resp.text
                    }, indent=2)
                return resp.text
            except Exception as e:
                return json.dumps({
                    "ok": False, 
                    "error": f"No se pudo invocar el backend interno en {path}. Detalles: {str(e)}"
                }, indent=2)

    try:
        if name == "check_floci_health":
            # Verificar backend en /health
            backend_ok = False
            backend_details = {}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                try:
                    resp = await client.get("/health")
                    if resp.status_code == 200:
                        backend_ok = True
                        backend_details = resp.json()
                except Exception as e:
                    backend_details = {"error": str(e)}

            from floci_backend.config import config
            # Verificar AWS endpoint (Localstack) - esto sí requiere HTTP a la red local
            aws_ok = False
            aws_details = {}
            aws_url = config.aws_endpoint_url
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    resp = await client.get(f"{aws_url}/_localstack/health")
                    if resp.status_code == 200:
                        aws_ok = True
                        aws_details = resp.json()
                except Exception as e:
                    aws_details = {"error": str(e)}

            result = {
                "backend": {
                    "status": "Online" if backend_ok else "Offline",
                    "details": backend_details
                },
                "aws_emulator": {
                    "status": "Online" if aws_ok else "Offline",
                    "url": aws_url,
                    "details": aws_details
                },
                "status": "Perfecto" if (backend_ok and aws_ok) else "Parcialmente disponible"
            }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_aws_services":
            response_text = await call_backend("GET", "/api/aws-services")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_service_resources":
            if not arguments or "serviceKey" not in arguments:
                raise ValueError("Se requiere el argumento 'serviceKey'")
            service_key = arguments["serviceKey"].lower()
            response_text = await call_backend("GET", f"/api/aws-services/{service_key}/overview")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "run_kms_diagnostic":
            response_text = await call_backend("GET", "/api/diagnostics/kms")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "list_marketplace_recipes":
            response_text = await call_backend("GET", "/api/marketplace/recipes")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_marketplace_installations":
            response_text = await call_backend("GET", "/api/marketplace/installations")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_marketplace_logs":
            if not arguments or "recipeId" not in arguments:
                raise ValueError("Se requiere el argumento 'recipeId'")
            recipe_id = arguments["recipeId"]
            response_text = await call_backend("GET", f"/api/marketplace/recipes/{recipe_id}/logs")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "deploy_marketplace_app":
            if not arguments or "recipeId" not in arguments:
                raise ValueError("Se requiere el argumento 'recipeId'")
            recipe_id = arguments["recipeId"]
            vars_data = arguments.get("vars", {})
            payload = {"recipeId": recipe_id, "vars": vars_data}
            response_text = await call_backend("POST", "/api/marketplace/install", json_data=payload)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "teardown_marketplace_app":
            if not arguments or "recipeId" not in arguments:
                raise ValueError("Se requiere el argumento 'recipeId'")
            recipe_id = arguments["recipeId"]
            response_text = await call_backend("DELETE", f"/api/marketplace/install/{recipe_id}")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "export_to_terraform":
            fmt = arguments.get("format", "terraform") if arguments else "terraform"
            response_text = await call_backend("GET", f"/api/extensions/export-iac?format={fmt}")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "run_local_aws_cmd":
            if not arguments or "command" not in arguments:
                raise ValueError("Se requiere el argumento 'command'")
            payload = {"command": arguments["command"]}
            response_text = await call_backend("POST", "/api/extensions/run-aws-cmd", json_data=payload)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "seed_mock_data":
            if not arguments or "target" not in arguments or "target_name" not in arguments:
                raise ValueError("Se requieren 'target' y 'target_name'")
            payload = {
                "target": arguments["target"],
                "target_name": arguments["target_name"],
                "connection_string": arguments.get("connection_string"),
                "custom_schema": arguments.get("custom_schema")
            }
            response_text = await call_backend("POST", "/api/extensions/seed-data", json_data=payload)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_network_topology":
            response_text = await call_backend("GET", "/api/extensions/network-topology")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "run_ui_tests":
            # Ejecutar npx playwright test directamente
            import subprocess
            import os
            import glob
            test_file = arguments.get("test_file", "") if arguments else ""
            cmd = ["npx", "playwright", "test"]
            if test_file:
                cmd.append(test_file)

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                output = stdout.decode()
                errors = stderr.decode()

                screenshots_msg = ""
                if process.returncode != 0:
                    # Find specific screenshots
                    test_results_dir = os.path.abspath("test-results")
                    screenshot_files = glob.glob(os.path.join(test_results_dir, "**", "*.png"), recursive=True)
                    if screenshot_files:
                        screenshots_msg = "\nCapturas de pantalla de fallos encontradas en las siguientes rutas absolutas:\n"
                        for sf in screenshot_files:
                            screenshots_msg += f"- {sf}\n"
                    else:
                        screenshots_msg = "\nNota: Pruebas fallaron, pero no se encontraron capturas de pantalla en test-results/."

                return [types.TextContent(type="text", text=f"Exit Code: {process.returncode}\n\nSTDOUT:\n{output}\nSTDERR:\n{errors}{screenshots_msg}")]
            except Exception as e:
                return [types.TextContent(type="text", text=f"Error al ejecutar los tests E2E: {str(e)}")]

        else:
            raise ValueError(f"Herramienta desconocida: {name}")

    except Exception as error:
        return [types.TextContent(type="text", text=json.dumps({"ok": False, "error": str(error)}, indent=2))]

async def main():
    # Arrancar el servidor MCP usando la entrada/salida estandar (stdio)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="floci-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
