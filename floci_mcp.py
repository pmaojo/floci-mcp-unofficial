import asyncio
import httpx
import os
import json
import sys
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Auto-deteccion inteligente si estamos corriendo dentro de un contenedor Docker
is_docker = os.path.exists('/.dockerenv') or os.environ.get("RUNNING_IN_DOCKER", "false").lower() == "true"

default_sidecar_url = "http://host.docker.internal:4317" if is_docker else "http://127.0.0.1:4317"
default_aws_url = "http://host.docker.internal:4566" if is_docker else "http://127.0.0.1:4566"

# Configuración leída de variables de entorno
SIDECAR_URL = os.environ.get("SIDECAR_URL", default_sidecar_url).rstrip("/")
SIDECAR_TOKEN = os.environ.get("SIDECAR_TOKEN", "open")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", default_aws_url).rstrip("/")

# Cabeceras requeridas para autorizar contra el Sidecar de Floci
headers = {
    "x-floci-sidecar-token": SIDECAR_TOKEN,
    "Content-Type": "application/json"
}

server = Server("floci-mcp")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Lista las herramientas de integracion disponibles en Floci, incluyendo orquestacion del Marketplace y AWS local."""
    return [
        types.Tool(
            name="check_floci_health",
            description="Verifica si el emulador local de AWS y el Sidecar de Floci estan respondiendo correctamente.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="list_aws_services",
            description="Lista todos los servicios soportados por Floci y su nivel de integracion (Nativo / Compatibilidad) en el cockpit.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="get_service_resources",
            description="Consulta el estado y los recursos reales de un servicio AWS especifico (ej. buckets S3, lambdas, colas sqs, etc.) consultando el Sidecar.",
            inputSchema={
                "type": "object",
                "properties": {
                    "serviceKey": {
                        "type": "string",
                        "description": "El identificador del servicio de AWS (ej. 's3', 'lambda', 'sqs', 'kms', 'dynamodb', 'sns')"
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
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str,
    arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Ejecuta una herramienta y devuelve la respuesta en formato de contenido MCP."""
    
    async def call_sidecar(method: str, path: str, json_data: dict = None) -> str:
        url = f"{SIDECAR_URL}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if method.upper() == "GET":
                    resp = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    resp = await client.post(url, headers=headers, json=json_data)
                elif method.upper() == "DELETE":
                    resp = await client.delete(url, headers=headers)
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
                    "error": f"No se pudo conectar con el Sidecar en {url}. Detalles: {str(e)}"
                }, indent=2)

    try:
        if name == "check_floci_health":
            # Verificar sidecar en /health
            url_health = f"{SIDECAR_URL}/health"
            sidecar_ok = False
            sidecar_details = {}
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    resp = await client.get(url_health)
                    if resp.status_code == 200:
                        sidecar_ok = True
                        sidecar_details = resp.json()
                except Exception as e:
                    sidecar_details = {"error": str(e)}

            # Verificar AWS endpoint (Localstack)
            aws_ok = False
            aws_details = {}
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    resp = await client.get(f"{AWS_ENDPOINT_URL}/_localstack/health")
                    if resp.status_code == 200:
                        aws_ok = True
                        aws_details = resp.json()
                except Exception as e:
                    aws_details = {"error": str(e)}

            result = {
                "sidecar": {
                    "status": "Online" if sidecar_ok else "Offline",
                    "url": SIDECAR_URL,
                    "details": sidecar_details
                },
                "aws_emulator": {
                    "status": "Online" if aws_ok else "Offline",
                    "url": AWS_ENDPOINT_URL,
                    "details": aws_details
                },
                "env_info": {
                    "is_container": is_docker,
                    "resolved_sidecar_url": SIDECAR_URL,
                    "resolved_aws_url": AWS_ENDPOINT_URL
                },
                "status": "Perfecto" if (sidecar_ok and aws_ok) else "Parcialmente disponible"
            }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_aws_services":
            response_text = await call_sidecar("GET", "/api/aws-services")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_service_resources":
            if not arguments or "serviceKey" not in arguments:
                raise ValueError("Se requiere el argumento 'serviceKey'")
            service_key = arguments["serviceKey"].lower()
            response_text = await call_sidecar("GET", f"/api/aws-services/{service_key}/overview")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "run_kms_diagnostic":
            response_text = await call_sidecar("GET", "/api/diagnostics/kms")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "list_marketplace_recipes":
            response_text = await call_sidecar("GET", "/api/marketplace/recipes")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_marketplace_installations":
            response_text = await call_sidecar("GET", "/api/marketplace/installations")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_marketplace_logs":
            if not arguments or "recipeId" not in arguments:
                raise ValueError("Se requiere el argumento 'recipeId'")
            recipe_id = arguments["recipeId"]
            response_text = await call_sidecar("GET", f"/api/marketplace/recipes/{recipe_id}/logs")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "deploy_marketplace_app":
            if not arguments or "recipeId" not in arguments:
                raise ValueError("Se requiere el argumento 'recipeId'")
            recipe_id = arguments["recipeId"]
            vars_data = arguments.get("vars", {})
            payload = {"recipeId": recipe_id, "vars": vars_data}
            response_text = await call_sidecar("POST", "/api/marketplace/install", json_data=payload)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "teardown_marketplace_app":
            if not arguments or "recipeId" not in arguments:
                raise ValueError("Se requiere el argumento 'recipeId'")
            recipe_id = arguments["recipeId"]
            response_text = await call_sidecar("DELETE", f"/api/marketplace/install/{recipe_id}")
            return [types.TextContent(type="text", text=response_text)]

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
