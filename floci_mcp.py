import asyncio
import base64
import json
import os
from datetime import datetime, date
from decimal import Decimal

import boto3
import httpx
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
import mcp.types as types

from floci_backend.config import config
from floci_backend.server import app

server = Server("floci-mcp")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_client(service: str):
    """Crea un cliente boto3 apuntando al emulador de Floci."""
    return boto3.client(
        service,
        endpoint_url=config.aws_endpoint_url,
        region_name=config.aws_region,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
    )


def _json(obj) -> str:
    """Serializa objetos boto3 (datetime, Decimal) a JSON."""
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, bytes):
            return base64.b64encode(o).decode()
        raise TypeError(f"No serializable: {type(o)}")
    return json.dumps(obj, indent=2, default=default)


def _ok(data) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=_json(data))]


def _err(msg: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps({"ok": False, "error": msg}, indent=2))]


async def _backend(method: str, path: str, json_data: dict = None) -> str:
    """Llama al backend FastAPI en memoria via ASGI transport."""
    headers = {}
    token = os.environ.get("SIDECAR_TOKEN")
    if token:
        headers["x-floci-sidecar-token"] = token

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        try:
            if method.upper() == "GET":
                resp = await client.get(path, headers=headers)
            elif method.upper() == "POST":
                resp = await client.post(path, headers=headers, json=json_data)
            elif method.upper() == "PUT":
                resp = await client.put(path, headers=headers, json=json_data)
            elif method.upper() == "DELETE":
                resp = await client.delete(path, headers=headers)
            else:
                return json.dumps({"ok": False, "error": f"Método HTTP {method} no soportado"})

            if resp.status_code >= 400:
                return json.dumps({"ok": False, "statusCode": resp.status_code, "error": resp.text}, indent=2)
            return resp.text
        except Exception as e:
            return json.dumps({"ok": False, "error": f"Error llamando al backend en {path}: {str(e)}"}, indent=2)


# ─── Tool catalog ─────────────────────────────────────────────────────────────

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [

        # ── Meta & Health ───────────────────────────────────────────────────
        types.Tool(
            name="check_floci_health",
            description="Verifica si el backend de Floci y el emulador de AWS están respondiendo.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="list_aws_services",
            description="Obtiene el catálogo completo de servicios AWS que Floci puede administrar.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_service_resources",
            description="Lee el inventario de recursos de un servicio AWS (ej. buckets S3, colas SQS, topics SNS).",
            inputSchema={
                "type": "object",
                "properties": {
                    "serviceKey": {"type": "string", "description": "Identificador del servicio (ej. 's3', 'lambda', 'sqs')"}
                },
                "required": ["serviceKey"],
            },
        ),
        types.Tool(
            name="get_architecture_diagram",
            description="Devuelve un diagrama Mermaid con todos los recursos activos del entorno (S3, SQS, DynamoDB, Lambda, API Gateway, KMS).",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_cost_forecast",
            description="Estima el coste mensual del entorno actual basado en los recursos existentes.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_network_topology",
            description="Devuelve un mapa Mermaid de la topología de red Docker local con puertos.",
            inputSchema={"type": "object", "properties": {}},
        ),

        # ── Developer Tools ─────────────────────────────────────────────────
        types.Tool(
            name="proxy_http_request",
            description="Envía una petición HTTP desde el backend de Floci (evita CORS). Útil para testear APIs locales.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL destino"},
                    "method": {"type": "string", "description": "Método HTTP (GET, POST, PUT, DELETE, PATCH). Por defecto GET"},
                    "headers": {"type": "object", "description": "Cabeceras HTTP opcionales"},
                    "body": {"description": "Cuerpo de la petición (objeto JSON o string)"},
                },
                "required": ["url"],
            },
        ),
        types.Tool(
            name="generate_jwt_token",
            description="Genera un JWT firmado con los claims especificados. Útil para autenticación en tests locales.",
            inputSchema={
                "type": "object",
                "properties": {
                    "claims": {"type": "object", "description": "Payload del JWT (sub, email, roles, exp, etc.)"},
                    "secret": {"type": "string", "description": "Clave de firma. Por defecto 'local-secret-key-123'"},
                    "algorithm": {"type": "string", "description": "Algoritmo de firma. Por defecto 'HS256'"},
                },
                "required": ["claims"],
            },
        ),
        types.Tool(
            name="export_to_terraform",
            description="Genera código Terraform o CDK a partir de los recursos actuales del emulador.",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {"type": "string", "description": "'terraform' o 'cdk'. Por defecto 'terraform'"}
                },
            },
        ),
        types.Tool(
            name="run_local_aws_cmd",
            description="Ejecuta un comando aws-cli directamente contra el emulador de Floci. Escape hatch para operaciones no cubiertas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando AWS CLI sin 'aws' inicial (ej. 's3 ls' o 'sqs list-queues')"}
                },
                "required": ["command"],
            },
        ),
        types.Tool(
            name="seed_mock_data",
            description="Inyecta datos sintéticos en DynamoDB, S3 o PostgreSQL del marketplace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "'postgres', 'dynamodb' o 's3'"},
                    "target_name": {"type": "string", "description": "Nombre de la tabla, bucket o base de datos"},
                    "connection_string": {"type": "string", "description": "Cadena de conexión PostgreSQL (solo para target=postgres)"},
                    "custom_schema": {"type": "object", "description": "Esquema JSON de ejemplo para generar los datos"},
                },
                "required": ["target", "target_name"],
            },
        ),
        types.Tool(
            name="run_ui_tests",
            description="Ejecuta tests Playwright del frontend y devuelve capturas de pantalla en caso de fallo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_file": {"type": "string", "description": "Ruta del test específico a ejecutar (opcional)"}
                },
            },
        ),
        types.Tool(
            name="run_kms_diagnostic",
            description="Ejecuta un test de cifrado/descifrado round-trip con KMS para verificar que funciona correctamente.",
            inputSchema={"type": "object", "properties": {}},
        ),

        # ── Marketplace ─────────────────────────────────────────────────────
        types.Tool(
            name="list_marketplace_recipes",
            description="Lista todas las recetas del Marketplace (postgres, redis, rabbitmq, keycloak, etc.) con sus variables configurables.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_marketplace_installations",
            description="Obtiene el estado de las instalaciones activas del Marketplace (RUNNING, INSTALLING, FAILED, IDLE).",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_marketplace_logs",
            description="Obtiene los logs de Docker Compose de una receta del Marketplace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipeId": {"type": "string", "description": "ID de la receta (ej. 'redis', 'postgres', 'rabbitmq')"}
                },
                "required": ["recipeId"],
            },
        ),
        types.Tool(
            name="deploy_marketplace_app",
            description="Instala y arranca una receta del Marketplace en Docker local.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipeId": {"type": "string", "description": "ID de la receta a instalar"},
                    "vars": {"type": "object", "description": "Variables de configuración (puertos, contraseñas, etc.)"},
                },
                "required": ["recipeId"],
            },
        ),
        types.Tool(
            name="teardown_marketplace_app",
            description="Detiene y elimina los contenedores de una receta del Marketplace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipeId": {"type": "string", "description": "ID de la receta a desinstalar"}
                },
                "required": ["recipeId"],
            },
        ),

        # ── Lambda ──────────────────────────────────────────────────────────
        types.Tool(
            name="get_lambda_runtimes",
            description="Lista los runtimes disponibles en Floci (Node.js, Python, Go, Java) y los templates de código por defecto.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="list_lambda_functions",
            description="Lista todas las funciones Lambda desplegadas en el entorno.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="create_lambda_function",
            description="Crea una nueva función Lambda con código inline, desde un template de runtime, o desde un ZIP en base64.",
            inputSchema={
                "type": "object",
                "properties": {
                    "functionName": {"type": "string", "description": "Nombre único de la función"},
                    "runtime": {"type": "string", "description": "Runtime (ej. 'nodejs18.x', 'python3.9', 'go1.x', 'java11')"},
                    "handler": {"type": "string", "description": "Handler de la función (ej. 'index.handler', 'main.handler')"},
                    "code": {
                        "type": "object",
                        "description": "Código fuente. Usa {'mode':'template'} para usar el template del runtime, {'mode':'inline','fileName':'index.js','source':'...'} para código inline, o {'mode':'zipBase64','zipBase64':'...'} para un ZIP en base64",
                    },
                    "description": {"type": "string", "description": "Descripción opcional de la función"},
                    "timeout": {"type": "integer", "description": "Timeout en segundos (1-900). Por defecto 30"},
                    "memorySize": {"type": "integer", "description": "Memoria en MB (128-10240). Por defecto 128"},
                },
                "required": ["functionName", "runtime", "handler", "code"],
            },
        ),
        types.Tool(
            name="update_lambda_code",
            description="Actualiza el código fuente de una función Lambda existente.",
            inputSchema={
                "type": "object",
                "properties": {
                    "functionName": {"type": "string", "description": "Nombre de la función"},
                    "runtime": {"type": "string", "description": "Runtime de la función"},
                    "code": {"type": "object", "description": "Nuevo código. Mismos formatos que create_lambda_function"},
                },
                "required": ["functionName", "runtime", "code"],
            },
        ),
        types.Tool(
            name="update_lambda_config",
            description="Actualiza la configuración de una función Lambda (timeout, memoria, handler, variables de entorno).",
            inputSchema={
                "type": "object",
                "properties": {
                    "functionName": {"type": "string", "description": "Nombre de la función"},
                    "handler": {"type": "string", "description": "Nuevo handler"},
                    "timeout": {"type": "integer", "description": "Nuevo timeout en segundos"},
                    "memorySize": {"type": "integer", "description": "Nueva memoria en MB"},
                    "description": {"type": "string", "description": "Nueva descripción"},
                },
                "required": ["functionName"],
            },
        ),
        types.Tool(
            name="invoke_lambda",
            description="Invoca una función Lambda con un payload JSON y devuelve la respuesta.",
            inputSchema={
                "type": "object",
                "properties": {
                    "functionName": {"type": "string", "description": "Nombre de la función a invocar"},
                    "payload": {"type": "object", "description": "Payload JSON para la función"},
                    "async": {"type": "boolean", "description": "Si true, invocación asíncrona (Event). Por defecto false (RequestResponse)"},
                },
                "required": ["functionName"],
            },
        ),
        types.Tool(
            name="get_lambda_logs",
            description="Obtiene los logs de CloudWatch de una función Lambda.",
            inputSchema={
                "type": "object",
                "properties": {
                    "functionName": {"type": "string", "description": "Nombre de la función"}
                },
                "required": ["functionName"],
            },
        ),
        types.Tool(
            name="delete_lambda",
            description="Elimina una función Lambda del entorno.",
            inputSchema={
                "type": "object",
                "properties": {
                    "functionName": {"type": "string", "description": "Nombre de la función a eliminar"}
                },
                "required": ["functionName"],
            },
        ),

        # ── SQS ─────────────────────────────────────────────────────────────
        types.Tool(
            name="list_sqs_queues",
            description="Lista todas las colas SQS del entorno con sus URLs.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="create_sqs_queue",
            description="Crea una cola SQS estándar o FIFO.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre de la cola. Las colas FIFO deben terminar en .fifo"},
                    "fifo": {"type": "boolean", "description": "Si true, crea una cola FIFO con ContentBasedDeduplication"},
                    "visibilityTimeout": {"type": "integer", "description": "Segundos que un mensaje queda invisible tras recibirlo (0-43200). Por defecto 30"},
                    "messageRetentionSeconds": {"type": "integer", "description": "Segundos que se retienen mensajes (60-1209600). Por defecto 345600 (4 días)"},
                    "delaySeconds": {"type": "integer", "description": "Segundos de retraso en entrega (0-900). Por defecto 0"},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="delete_sqs_queue",
            description="Elimina una cola SQS y todos sus mensajes de forma permanente.",
            inputSchema={
                "type": "object",
                "properties": {
                    "queueUrl": {"type": "string", "description": "URL de la cola SQS"}
                },
                "required": ["queueUrl"],
            },
        ),
        types.Tool(
            name="send_sqs_message",
            description="Envía un mensaje a una cola SQS.",
            inputSchema={
                "type": "object",
                "properties": {
                    "queueUrl": {"type": "string", "description": "URL de la cola destino"},
                    "body": {"type": "string", "description": "Cuerpo del mensaje (string o JSON serializado)"},
                    "messageGroupId": {"type": "string", "description": "Requerido para colas FIFO. Agrupa mensajes relacionados"},
                    "messageDeduplicationId": {"type": "string", "description": "ID de deduplicación para colas FIFO sin ContentBasedDeduplication"},
                    "delaySeconds": {"type": "integer", "description": "Retraso de entrega en segundos (0-900, solo para colas estándar)"},
                },
                "required": ["queueUrl", "body"],
            },
        ),
        types.Tool(
            name="receive_sqs_messages",
            description="Recibe y devuelve mensajes de una cola SQS. Los mensajes quedan invisibles hasta que se eliminen con delete_sqs_message.",
            inputSchema={
                "type": "object",
                "properties": {
                    "queueUrl": {"type": "string", "description": "URL de la cola"},
                    "maxMessages": {"type": "integer", "description": "Número máximo de mensajes a recibir (1-10). Por defecto 10"},
                    "waitSeconds": {"type": "integer", "description": "Long polling: segundos de espera si no hay mensajes (0-20). Por defecto 0"},
                    "visibilityTimeout": {"type": "integer", "description": "Segundos que los mensajes quedan invisibles (0-43200)"},
                },
                "required": ["queueUrl"],
            },
        ),
        types.Tool(
            name="delete_sqs_message",
            description="Elimina un mensaje de una cola SQS usando su ReceiptHandle (obtenido con receive_sqs_messages).",
            inputSchema={
                "type": "object",
                "properties": {
                    "queueUrl": {"type": "string", "description": "URL de la cola"},
                    "receiptHandle": {"type": "string", "description": "ReceiptHandle del mensaje (obtenido al recibirlo)"},
                },
                "required": ["queueUrl", "receiptHandle"],
            },
        ),
        types.Tool(
            name="get_sqs_queue_attributes",
            description="Obtiene los atributos de una cola SQS: número de mensajes disponibles, invisibles, DLQ configurada, timeouts, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "queueUrl": {"type": "string", "description": "URL de la cola"}
                },
                "required": ["queueUrl"],
            },
        ),
        types.Tool(
            name="purge_sqs_queue",
            description="Elimina todos los mensajes de una cola SQS instantáneamente (la cola permanece).",
            inputSchema={
                "type": "object",
                "properties": {
                    "queueUrl": {"type": "string", "description": "URL de la cola a vaciar"}
                },
                "required": ["queueUrl"],
            },
        ),

        # ── SNS ─────────────────────────────────────────────────────────────
        types.Tool(
            name="list_sns_topics",
            description="Lista todos los topics SNS del entorno con sus ARNs.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="create_sns_topic",
            description="Crea un topic SNS estándar o FIFO.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre del topic. Los topics FIFO deben terminar en .fifo"},
                    "fifo": {"type": "boolean", "description": "Si true, crea un topic FIFO con ContentBasedDeduplication"},
                    "displayName": {"type": "string", "description": "Nombre visible para emails (DisplayName del topic)"},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="delete_sns_topic",
            description="Elimina un topic SNS y todas sus subscripciones.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topicArn": {"type": "string", "description": "ARN del topic a eliminar"}
                },
                "required": ["topicArn"],
            },
        ),
        types.Tool(
            name="publish_sns_message",
            description="Publica un mensaje en un topic SNS, distribuyéndolo a todos los suscriptores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topicArn": {"type": "string", "description": "ARN del topic destino"},
                    "message": {"type": "string", "description": "Cuerpo del mensaje"},
                    "subject": {"type": "string", "description": "Asunto del mensaje (visible en emails)"},
                    "messageAttributes": {
                        "type": "object",
                        "description": "Atributos del mensaje para filtrado. Formato: {'key': {'DataType': 'String', 'StringValue': 'val'}}",
                    },
                },
                "required": ["topicArn", "message"],
            },
        ),
        types.Tool(
            name="list_sns_subscriptions",
            description="Lista todas las subscripciones de un topic SNS (protocolo, endpoint, estado).",
            inputSchema={
                "type": "object",
                "properties": {
                    "topicArn": {"type": "string", "description": "ARN del topic"}
                },
                "required": ["topicArn"],
            },
        ),
        types.Tool(
            name="subscribe_sns",
            description="Suscribe un endpoint a un topic SNS. Soporta email, SQS, Lambda, HTTP/HTTPS y SMS.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topicArn": {"type": "string", "description": "ARN del topic"},
                    "protocol": {"type": "string", "description": "Protocolo: 'email', 'email-json', 'sqs', 'lambda', 'http', 'https', 'sms'"},
                    "endpoint": {"type": "string", "description": "Endpoint destino (email, ARN de SQS/Lambda, URL HTTP, número de teléfono)"},
                },
                "required": ["topicArn", "protocol", "endpoint"],
            },
        ),
        types.Tool(
            name="unsubscribe_sns",
            description="Elimina una subscripción de un topic SNS.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscriptionArn": {"type": "string", "description": "ARN de la subscripción a eliminar"}
                },
                "required": ["subscriptionArn"],
            },
        ),
        types.Tool(
            name="get_sns_topic_attributes",
            description="Obtiene los atributos de un topic SNS (nombre, política, tipo FIFO, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "topicArn": {"type": "string", "description": "ARN del topic"}
                },
                "required": ["topicArn"],
            },
        ),

        # ── S3 ──────────────────────────────────────────────────────────────
        types.Tool(
            name="list_s3_buckets",
            description="Lista todos los buckets S3 del entorno.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="create_s3_bucket",
            description="Crea un nuevo bucket S3.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre del bucket (único globalmente, solo minúsculas y guiones)"},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="delete_s3_bucket",
            description="Elimina un bucket S3. Si force=true, vacía el bucket antes de eliminarlo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre del bucket"},
                    "force": {"type": "boolean", "description": "Si true, elimina todos los objetos antes de borrar el bucket"},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="list_s3_objects",
            description="Lista los objetos de un bucket S3, con filtro opcional por prefijo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Nombre del bucket"},
                    "prefix": {"type": "string", "description": "Prefijo para filtrar objetos (ej. 'data/', 'logs/2024/')"},
                    "maxKeys": {"type": "integer", "description": "Número máximo de objetos a listar. Por defecto 100"},
                },
                "required": ["bucket"],
            },
        ),
        types.Tool(
            name="put_s3_object",
            description="Sube o sobreescribe un objeto en S3 con contenido en texto o JSON.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Nombre del bucket"},
                    "key": {"type": "string", "description": "Ruta/nombre del objeto (ej. 'data/file.json')"},
                    "content": {"type": "string", "description": "Contenido del objeto como string (o JSON serializado)"},
                    "contentType": {"type": "string", "description": "MIME type (ej. 'application/json', 'text/plain'). Por defecto 'text/plain'"},
                },
                "required": ["bucket", "key", "content"],
            },
        ),
        types.Tool(
            name="get_s3_object",
            description="Descarga y devuelve el contenido de un objeto S3 como texto.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Nombre del bucket"},
                    "key": {"type": "string", "description": "Ruta/nombre del objeto"},
                },
                "required": ["bucket", "key"],
            },
        ),
        types.Tool(
            name="delete_s3_object",
            description="Elimina un objeto de un bucket S3.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Nombre del bucket"},
                    "key": {"type": "string", "description": "Ruta/nombre del objeto a eliminar"},
                },
                "required": ["bucket", "key"],
            },
        ),
        types.Tool(
            name="generate_s3_presigned_url",
            description="Genera una URL pre-firmada para acceso temporal a un objeto S3 (sin autenticación).",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Nombre del bucket"},
                    "key": {"type": "string", "description": "Ruta/nombre del objeto"},
                    "operation": {"type": "string", "description": "'get_object' para descarga o 'put_object' para subida. Por defecto 'get_object'"},
                    "expiresIn": {"type": "integer", "description": "Segundos de validez de la URL (60-604800). Por defecto 3600"},
                },
                "required": ["bucket", "key"],
            },
        ),

        # ── DynamoDB ─────────────────────────────────────────────────────────
        types.Tool(
            name="list_dynamodb_tables",
            description="Lista todas las tablas DynamoDB del entorno.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="create_dynamodb_table",
            description="Crea una tabla DynamoDB con clave de partición y opcionalmente clave de ordenación.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre de la tabla"},
                    "partitionKey": {"type": "string", "description": "Nombre del atributo de clave de partición"},
                    "partitionKeyType": {"type": "string", "description": "Tipo de la clave de partición: 'S' (String), 'N' (Number), 'B' (Binary). Por defecto 'S'"},
                    "sortKey": {"type": "string", "description": "Nombre del atributo de clave de ordenación (opcional)"},
                    "sortKeyType": {"type": "string", "description": "Tipo de la clave de ordenación: 'S', 'N' o 'B'. Por defecto 'S'"},
                    "billingMode": {"type": "string", "description": "'PAY_PER_REQUEST' o 'PROVISIONED'. Por defecto 'PAY_PER_REQUEST'"},
                },
                "required": ["name", "partitionKey"],
            },
        ),
        types.Tool(
            name="delete_dynamodb_table",
            description="Elimina una tabla DynamoDB y todos sus datos.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre de la tabla"}
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="put_dynamodb_item",
            description="Inserta o reemplaza un ítem en una tabla DynamoDB. El ítem debe usar el formato de atributos de DynamoDB: {'campo': {'S': 'valor'}, 'numero': {'N': '42'}}.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Nombre de la tabla"},
                    "item": {"type": "object", "description": "Ítem en formato DynamoDB: {'pk': {'S': 'val'}, 'count': {'N': '1'}}"},
                },
                "required": ["table", "item"],
            },
        ),
        types.Tool(
            name="get_dynamodb_item",
            description="Obtiene un ítem específico de DynamoDB por su clave primaria.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Nombre de la tabla"},
                    "key": {"type": "object", "description": "Clave primaria en formato DynamoDB: {'pk': {'S': 'valor'}}"},
                },
                "required": ["table", "key"],
            },
        ),
        types.Tool(
            name="query_dynamodb",
            description="Consulta ítems en DynamoDB usando la clave de partición. Opcionalmente filtra por clave de ordenación.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Nombre de la tabla"},
                    "keyConditionExpression": {"type": "string", "description": "Expresión de condición (ej. 'pk = :pk')"},
                    "expressionAttributeValues": {"type": "object", "description": "Valores de la expresión en formato DynamoDB (ej. {':pk': {'S': 'user-1'}})"},
                    "filterExpression": {"type": "string", "description": "Filtro adicional sobre atributos no clave"},
                    "limit": {"type": "integer", "description": "Número máximo de ítems a devolver"},
                    "scanIndexForward": {"type": "boolean", "description": "Si false, ordena descendentemente. Por defecto true"},
                },
                "required": ["table", "keyConditionExpression", "expressionAttributeValues"],
            },
        ),
        types.Tool(
            name="scan_dynamodb",
            description="Escanea todos los ítems de una tabla DynamoDB. Para datasets grandes, usar query_dynamodb.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Nombre de la tabla"},
                    "filterExpression": {"type": "string", "description": "Expresión de filtro sobre los resultados"},
                    "expressionAttributeValues": {"type": "object", "description": "Valores de la expresión en formato DynamoDB"},
                    "limit": {"type": "integer", "description": "Número máximo de ítems a devolver"},
                },
                "required": ["table"],
            },
        ),
        types.Tool(
            name="delete_dynamodb_item",
            description="Elimina un ítem específico de una tabla DynamoDB por su clave primaria.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Nombre de la tabla"},
                    "key": {"type": "object", "description": "Clave primaria en formato DynamoDB: {'pk': {'S': 'valor'}}"},
                },
                "required": ["table", "key"],
            },
        ),

        # ── Secrets Manager ──────────────────────────────────────────────────
        types.Tool(
            name="list_secrets",
            description="Lista todos los secretos de AWS Secrets Manager.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="create_secret",
            description="Crea un nuevo secreto en Secrets Manager.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre del secreto"},
                    "value": {"type": "string", "description": "Valor del secreto (string o JSON serializado)"},
                    "description": {"type": "string", "description": "Descripción del secreto"},
                },
                "required": ["name", "value"],
            },
        ),
        types.Tool(
            name="get_secret_value",
            description="Obtiene el valor de un secreto de Secrets Manager.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nameOrArn": {"type": "string", "description": "Nombre o ARN del secreto"}
                },
                "required": ["nameOrArn"],
            },
        ),
        types.Tool(
            name="update_secret",
            description="Actualiza el valor de un secreto existente en Secrets Manager.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nameOrArn": {"type": "string", "description": "Nombre o ARN del secreto"},
                    "value": {"type": "string", "description": "Nuevo valor del secreto"},
                },
                "required": ["nameOrArn", "value"],
            },
        ),
        types.Tool(
            name="delete_secret",
            description="Elimina un secreto de Secrets Manager.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nameOrArn": {"type": "string", "description": "Nombre o ARN del secreto"},
                    "force": {"type": "boolean", "description": "Si true, elimina inmediatamente sin período de recuperación"},
                },
                "required": ["nameOrArn"],
            },
        ),

        # ── KMS ──────────────────────────────────────────────────────────────
        types.Tool(
            name="list_kms_keys",
            description="Lista todas las claves KMS del entorno con sus aliases.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="create_kms_key",
            description="Crea una nueva clave de cifrado KMS con alias opcional.",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Descripción de la clave"},
                    "alias": {"type": "string", "description": "Alias de la clave (ej. 'alias/mi-clave'). Debe empezar con 'alias/'"},
                },
            },
        ),
        types.Tool(
            name="kms_encrypt",
            description="Cifra texto plano con una clave KMS. Devuelve el ciphertext en base64.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyId": {"type": "string", "description": "ID, ARN o alias de la clave KMS"},
                    "plaintext": {"type": "string", "description": "Texto a cifrar"},
                },
                "required": ["keyId", "plaintext"],
            },
        ),
        types.Tool(
            name="kms_decrypt",
            description="Descifra un ciphertext KMS (en base64) y devuelve el texto plano.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ciphertextBlob": {"type": "string", "description": "Ciphertext en base64 (obtenido con kms_encrypt)"}
                },
                "required": ["ciphertextBlob"],
            },
        ),

        # ── EventBridge ──────────────────────────────────────────────────────
        types.Tool(
            name="list_eventbridge_buses",
            description="Lista todos los event buses de EventBridge (incluyendo el bus 'default').",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="put_eventbridge_events",
            description="Envía eventos personalizados a un event bus de EventBridge. Útil para testear reglas y triggers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entries": {
                        "type": "array",
                        "description": "Lista de eventos. Cada evento: {'Source': 'mi.app', 'DetailType': 'OrderCreated', 'Detail': '{\"orderId\":\"123\"}', 'EventBusName': 'default'}",
                        "items": {"type": "object"},
                    }
                },
                "required": ["entries"],
            },
        ),
        types.Tool(
            name="list_eventbridge_rules",
            description="Lista las reglas de un event bus de EventBridge.",
            inputSchema={
                "type": "object",
                "properties": {
                    "busName": {"type": "string", "description": "Nombre del event bus. Por defecto 'default'"}
                },
            },
        ),
        types.Tool(
            name="create_eventbridge_rule",
            description="Crea una regla de EventBridge con un patrón de eventos o expresión cron/rate, y opcionalmente añade targets (Lambda, SQS, SNS).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre de la regla"},
                    "scheduleExpression": {"type": "string", "description": "Expresión de schedule (ej. 'rate(5 minutes)' o 'cron(0 12 * * ? *)'). Mutuamente exclusivo con eventPattern"},
                    "eventPattern": {"type": "string", "description": "Patrón JSON de eventos (ej. '{\"source\":[\"mi.app\"]}). Mutuamente exclusivo con scheduleExpression"},
                    "busName": {"type": "string", "description": "Nombre del event bus. Por defecto 'default'"},
                    "targets": {
                        "type": "array",
                        "description": "Targets de la regla. Ej: [{'Id':'t1','Arn':'arn:aws:lambda:...:function:mi-fn'}]",
                        "items": {"type": "object"},
                    },
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="delete_eventbridge_rule",
            description="Elimina una regla de EventBridge (primero elimina sus targets automáticamente).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre de la regla"},
                    "busName": {"type": "string", "description": "Nombre del event bus. Por defecto 'default'"},
                },
                "required": ["name"],
            },
        ),

        # ── Step Functions ────────────────────────────────────────────────────
        types.Tool(
            name="list_step_functions",
            description="Lista todas las state machines de AWS Step Functions.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="start_sfn_execution",
            description="Inicia una ejecución de una state machine de Step Functions con un input JSON.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stateMachineArn": {"type": "string", "description": "ARN de la state machine"},
                    "input": {"type": "object", "description": "Input JSON para la ejecución"},
                    "name": {"type": "string", "description": "Nombre único para la ejecución (opcional)"},
                },
                "required": ["stateMachineArn"],
            },
        ),
        types.Tool(
            name="describe_sfn_execution",
            description="Obtiene el estado, input, output y duración de una ejecución de Step Functions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "executionArn": {"type": "string", "description": "ARN de la ejecución"}
                },
                "required": ["executionArn"],
            },
        ),
        types.Tool(
            name="list_sfn_executions",
            description="Lista las ejecuciones de una state machine de Step Functions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stateMachineArn": {"type": "string", "description": "ARN de la state machine"},
                    "statusFilter": {"type": "string", "description": "Filtrar por estado: 'RUNNING', 'SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED'"},
                    "maxResults": {"type": "integer", "description": "Número máximo de resultados. Por defecto 20"},
                },
                "required": ["stateMachineArn"],
            },
        ),

        # ── Athena ───────────────────────────────────────────────────────────
        types.Tool(
            name="list_glue_databases",
            description="Lista las bases de datos y tablas del catálogo de datos de AWS Glue (usado por Athena).",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="run_athena_query",
            description="Ejecuta una consulta SQL en Athena y espera el resultado. Devuelve las filas directamente.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "Consulta SQL a ejecutar"},
                    "database": {"type": "string", "description": "Base de datos de Glue sobre la que ejecutar"},
                    "workgroup": {"type": "string", "description": "Workgroup de Athena. Por defecto 'primary'"},
                    "timeoutSeconds": {"type": "integer", "description": "Máximo de segundos de espera. Por defecto 30"},
                },
                "required": ["sql"],
            },
        ),
        types.Tool(
            name="get_athena_query_history",
            description="Obtiene el historial de consultas Athena ejecutadas en esta sesión.",
            inputSchema={"type": "object", "properties": {}},
        ),

        # ── SES ──────────────────────────────────────────────────────────────
        types.Tool(
            name="list_ses_identities",
            description="Lista todas las identidades verificadas en SES (emails y dominios).",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="verify_ses_email",
            description="Inicia la verificación de un email en SES. En entornos locales se verifica automáticamente.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Dirección de email a verificar"}
                },
                "required": ["email"],
            },
        ),
        types.Tool(
            name="send_ses_email",
            description="Envía un email a través de SES. El remitente debe estar verificado.",
            inputSchema={
                "type": "object",
                "properties": {
                    "fromAddress": {"type": "string", "description": "Dirección de origen (debe estar verificada en SES)"},
                    "toAddresses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de destinatarios",
                    },
                    "subject": {"type": "string", "description": "Asunto del email"},
                    "bodyText": {"type": "string", "description": "Cuerpo del email en texto plano"},
                    "bodyHtml": {"type": "string", "description": "Cuerpo del email en HTML (opcional, complementa bodyText)"},
                    "ccAddresses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Destinatarios en copia (CC)",
                    },
                },
                "required": ["fromAddress", "toAddresses", "subject", "bodyText"],
            },
        ),
        types.Tool(
            name="get_ses_send_quota",
            description="Obtiene las estadísticas de envío de SES: cuota máxima, tasa de envío y emails enviados hoy.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


# ─── Tool handlers ────────────────────────────────────────────────────────────

@server.call_tool()
async def handle_call_tool(
    name: str,
    arguments: dict | None,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:

    args = arguments or {}

    try:

        # ── Meta & Health ────────────────────────────────────────────────────
        if name == "check_floci_health":
            backend_ok, backend_details = False, {}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
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

            return _ok({
                "backend": {"status": "Online" if backend_ok else "Offline", "details": backend_details},
                "aws_emulator": {"status": "Online" if aws_ok else "Offline", "url": config.aws_endpoint_url, "details": aws_details},
                "overall": "OK" if (backend_ok and aws_ok) else "Degradado",
            })

        elif name == "list_aws_services":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/aws-services"))]

        elif name == "get_service_resources":
            key = args.get("serviceKey", "").lower()
            if not key:
                return _err("Se requiere 'serviceKey'")
            return [types.TextContent(type="text", text=await _backend("GET", f"/api/aws-services/{key}/overview"))]

        elif name == "get_architecture_diagram":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/studio/architecture"))]

        elif name == "get_cost_forecast":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/diagnostics/cost-forecast"))]

        elif name == "get_network_topology":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/extensions/network-topology"))]

        # ── Developer Tools ──────────────────────────────────────────────────
        elif name == "proxy_http_request":
            if not args.get("url"):
                return _err("Se requiere 'url'")
            payload = {
                "url": args["url"],
                "method": args.get("method", "GET"),
                "headers": args.get("headers"),
                "body": args.get("body"),
            }
            return [types.TextContent(type="text", text=await _backend("POST", "/api/studio/client/proxy", json_data=payload))]

        elif name == "generate_jwt_token":
            if not args.get("claims"):
                return _err("Se requiere 'claims'")
            payload = {
                "claims": args["claims"],
                "secret": args.get("secret", "local-secret-key-123"),
                "algorithm": args.get("algorithm", "HS256"),
            }
            return [types.TextContent(type="text", text=await _backend("POST", "/api/studio/auth/generate-token", json_data=payload))]

        elif name == "export_to_terraform":
            fmt = args.get("format", "terraform")
            return [types.TextContent(type="text", text=await _backend("GET", f"/api/extensions/export-iac?format={fmt}"))]

        elif name == "run_local_aws_cmd":
            if not args.get("command"):
                return _err("Se requiere 'command'")
            return [types.TextContent(type="text", text=await _backend("POST", "/api/extensions/run-aws-cmd", json_data={"command": args["command"]}))]

        elif name == "seed_mock_data":
            if not args.get("target") or not args.get("target_name"):
                return _err("Se requieren 'target' y 'target_name'")
            return [types.TextContent(type="text", text=await _backend("POST", "/api/extensions/seed-data", json_data={
                "target": args["target"],
                "target_name": args["target_name"],
                "connection_string": args.get("connection_string"),
                "custom_schema": args.get("custom_schema"),
            }))]

        elif name == "run_kms_diagnostic":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/diagnostics/kms"))]

        elif name == "run_ui_tests":
            import glob
            test_file = args.get("test_file", "")
            cmd = ["npx", "playwright", "test"]
            if test_file:
                cmd.append(test_file)
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode()
            errors = stderr.decode()
            screenshots = ""
            if process.returncode != 0:
                shots = glob.glob(os.path.join(os.path.abspath("test-results"), "**", "*.png"), recursive=True)
                if shots:
                    screenshots = "\nCapturas:\n" + "\n".join(f"- {s}" for s in shots)
            return [types.TextContent(type="text", text=f"Exit: {process.returncode}\n\nSTDOUT:\n{output}\nSTDERR:\n{errors}{screenshots}")]

        # ── Marketplace ──────────────────────────────────────────────────────
        elif name == "list_marketplace_recipes":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/marketplace/recipes"))]

        elif name == "get_marketplace_installations":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/marketplace/installations"))]

        elif name == "get_marketplace_logs":
            recipe_id = args.get("recipeId")
            if not recipe_id:
                return _err("Se requiere 'recipeId'")
            return [types.TextContent(type="text", text=await _backend("GET", f"/api/marketplace/recipes/{recipe_id}/logs"))]

        elif name == "deploy_marketplace_app":
            recipe_id = args.get("recipeId")
            if not recipe_id:
                return _err("Se requiere 'recipeId'")
            return [types.TextContent(type="text", text=await _backend("POST", "/api/marketplace/install", json_data={"recipeId": recipe_id, "vars": args.get("vars", {})}))]

        elif name == "teardown_marketplace_app":
            recipe_id = args.get("recipeId")
            if not recipe_id:
                return _err("Se requiere 'recipeId'")
            return [types.TextContent(type="text", text=await _backend("DELETE", f"/api/marketplace/install/{recipe_id}"))]

        # ── Lambda ───────────────────────────────────────────────────────────
        elif name == "get_lambda_runtimes":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/lambda/capabilities"))]

        elif name == "list_lambda_functions":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/lambda/functions"))]

        elif name == "create_lambda_function":
            required = ["functionName", "runtime", "handler", "code"]
            if not all(k in args for k in required):
                return _err(f"Se requieren: {required}")
            payload = {
                "functionName": args["functionName"],
                "runtime": args["runtime"],
                "handler": args["handler"],
                "code": args["code"],
                "description": args.get("description", ""),
                "timeout": args.get("timeout", 30),
                "memorySize": args.get("memorySize", 128),
            }
            return [types.TextContent(type="text", text=await _backend("POST", "/api/lambda/functions", json_data=payload))]

        elif name == "update_lambda_code":
            fn = args.get("functionName")
            if not fn or not args.get("runtime") or not args.get("code"):
                return _err("Se requieren 'functionName', 'runtime' y 'code'")
            return [types.TextContent(type="text", text=await _backend("PUT", f"/api/lambda/functions/{fn}/code", json_data={"runtime": args["runtime"], "code": args["code"]}))]

        elif name == "update_lambda_config":
            fn = args.get("functionName")
            if not fn:
                return _err("Se requiere 'functionName'")
            payload = {k: args[k] for k in ["handler", "timeout", "memorySize", "description"] if k in args}
            return [types.TextContent(type="text", text=await _backend("PUT", f"/api/lambda/functions/{fn}/configuration", json_data=payload))]

        elif name == "invoke_lambda":
            fn = args.get("functionName")
            if not fn:
                return _err("Se requiere 'functionName'")
            payload = {
                "payload": args.get("payload", {}),
                "async": args.get("async", False),
            }
            return [types.TextContent(type="text", text=await _backend("POST", f"/api/lambda/functions/{fn}/invoke", json_data=payload))]

        elif name == "get_lambda_logs":
            fn = args.get("functionName")
            if not fn:
                return _err("Se requiere 'functionName'")
            return [types.TextContent(type="text", text=await _backend("GET", f"/api/lambda/functions/{fn}/logs"))]

        elif name == "delete_lambda":
            fn = args.get("functionName")
            if not fn:
                return _err("Se requiere 'functionName'")
            return [types.TextContent(type="text", text=await _backend("DELETE", f"/api/lambda/functions/{fn}"))]

        # ── SQS ──────────────────────────────────────────────────────────────
        elif name == "list_sqs_queues":
            c = _make_client("sqs")
            r = c.list_queues()
            return _ok({"queues": r.get("QueueUrls", [])})

        elif name == "create_sqs_queue":
            qname = args.get("name")
            if not qname:
                return _err("Se requiere 'name'")
            fifo = args.get("fifo", False)
            if fifo and not qname.endswith(".fifo"):
                qname = qname + ".fifo"
            attrs = {}
            if fifo:
                attrs["FifoQueue"] = "true"
                attrs["ContentBasedDeduplication"] = "true"
            if "visibilityTimeout" in args:
                attrs["VisibilityTimeout"] = str(args["visibilityTimeout"])
            if "messageRetentionSeconds" in args:
                attrs["MessageRetentionPeriod"] = str(args["messageRetentionSeconds"])
            if "delaySeconds" in args:
                attrs["DelaySeconds"] = str(args["delaySeconds"])
            c = _make_client("sqs")
            r = c.create_queue(QueueName=qname, Attributes=attrs)
            return _ok({"queueUrl": r["QueueUrl"], "name": qname})

        elif name == "delete_sqs_queue":
            url = args.get("queueUrl")
            if not url:
                return _err("Se requiere 'queueUrl'")
            c = _make_client("sqs")
            c.delete_queue(QueueUrl=url)
            return _ok({"deleted": url})

        elif name == "send_sqs_message":
            url = args.get("queueUrl")
            body = args.get("body")
            if not url or body is None:
                return _err("Se requieren 'queueUrl' y 'body'")
            c = _make_client("sqs")
            params = {"QueueUrl": url, "MessageBody": body}
            if "messageGroupId" in args:
                params["MessageGroupId"] = args["messageGroupId"]
            if "messageDeduplicationId" in args:
                params["MessageDeduplicationId"] = args["messageDeduplicationId"]
            if "delaySeconds" in args:
                params["DelaySeconds"] = args["delaySeconds"]
            r = c.send_message(**params)
            return _ok({"messageId": r["MessageId"], "md5": r.get("MD5OfMessageBody")})

        elif name == "receive_sqs_messages":
            url = args.get("queueUrl")
            if not url:
                return _err("Se requiere 'queueUrl'")
            c = _make_client("sqs")
            params = {
                "QueueUrl": url,
                "MaxNumberOfMessages": min(args.get("maxMessages", 10), 10),
                "WaitTimeSeconds": args.get("waitSeconds", 0),
                "AttributeNames": ["All"],
                "MessageAttributeNames": ["All"],
            }
            if "visibilityTimeout" in args:
                params["VisibilityTimeout"] = args["visibilityTimeout"]
            r = c.receive_message(**params)
            messages = r.get("Messages", [])
            return _ok({"count": len(messages), "messages": messages})

        elif name == "delete_sqs_message":
            url = args.get("queueUrl")
            receipt = args.get("receiptHandle")
            if not url or not receipt:
                return _err("Se requieren 'queueUrl' y 'receiptHandle'")
            c = _make_client("sqs")
            c.delete_message(QueueUrl=url, ReceiptHandle=receipt)
            return _ok({"deleted": True})

        elif name == "get_sqs_queue_attributes":
            url = args.get("queueUrl")
            if not url:
                return _err("Se requiere 'queueUrl'")
            c = _make_client("sqs")
            r = c.get_queue_attributes(QueueUrl=url, AttributeNames=["All"])
            return _ok(r.get("Attributes", {}))

        elif name == "purge_sqs_queue":
            url = args.get("queueUrl")
            if not url:
                return _err("Se requiere 'queueUrl'")
            c = _make_client("sqs")
            c.purge_queue(QueueUrl=url)
            return _ok({"purged": url})

        # ── SNS ──────────────────────────────────────────────────────────────
        elif name == "list_sns_topics":
            c = _make_client("sns")
            r = c.list_topics()
            return _ok({"topics": r.get("Topics", [])})

        elif name == "create_sns_topic":
            tname = args.get("name")
            if not tname:
                return _err("Se requiere 'name'")
            fifo = args.get("fifo", False)
            if fifo and not tname.endswith(".fifo"):
                tname = tname + ".fifo"
            attrs = {}
            if fifo:
                attrs["FifoTopic"] = "true"
                attrs["ContentBasedDeduplication"] = "true"
            if "displayName" in args:
                attrs["DisplayName"] = args["displayName"]
            c = _make_client("sns")
            r = c.create_topic(Name=tname, Attributes=attrs)
            return _ok({"topicArn": r["TopicArn"], "name": tname})

        elif name == "delete_sns_topic":
            arn = args.get("topicArn")
            if not arn:
                return _err("Se requiere 'topicArn'")
            c = _make_client("sns")
            c.delete_topic(TopicArn=arn)
            return _ok({"deleted": arn})

        elif name == "publish_sns_message":
            arn = args.get("topicArn")
            msg = args.get("message")
            if not arn or not msg:
                return _err("Se requieren 'topicArn' y 'message'")
            c = _make_client("sns")
            params = {"TopicArn": arn, "Message": msg}
            if "subject" in args:
                params["Subject"] = args["subject"]
            if "messageAttributes" in args:
                params["MessageAttributes"] = args["messageAttributes"]
            r = c.publish(**params)
            return _ok({"messageId": r["MessageId"]})

        elif name == "list_sns_subscriptions":
            arn = args.get("topicArn")
            if not arn:
                return _err("Se requiere 'topicArn'")
            c = _make_client("sns")
            r = c.list_subscriptions_by_topic(TopicArn=arn)
            return _ok({"subscriptions": r.get("Subscriptions", [])})

        elif name == "subscribe_sns":
            arn = args.get("topicArn")
            protocol = args.get("protocol")
            endpoint = args.get("endpoint")
            if not arn or not protocol or not endpoint:
                return _err("Se requieren 'topicArn', 'protocol' y 'endpoint'")
            c = _make_client("sns")
            r = c.subscribe(TopicArn=arn, Protocol=protocol, Endpoint=endpoint)
            return _ok({"subscriptionArn": r.get("SubscriptionArn")})

        elif name == "unsubscribe_sns":
            sub_arn = args.get("subscriptionArn")
            if not sub_arn:
                return _err("Se requiere 'subscriptionArn'")
            c = _make_client("sns")
            c.unsubscribe(SubscriptionArn=sub_arn)
            return _ok({"unsubscribed": sub_arn})

        elif name == "get_sns_topic_attributes":
            arn = args.get("topicArn")
            if not arn:
                return _err("Se requiere 'topicArn'")
            c = _make_client("sns")
            r = c.get_topic_attributes(TopicArn=arn)
            return _ok(r.get("Attributes", {}))

        # ── S3 ───────────────────────────────────────────────────────────────
        elif name == "list_s3_buckets":
            c = _make_client("s3")
            r = c.list_buckets()
            return _ok({"buckets": [b["Name"] for b in r.get("Buckets", [])]})

        elif name == "create_s3_bucket":
            bname = args.get("name")
            if not bname:
                return _err("Se requiere 'name'")
            c = _make_client("s3")
            if config.aws_region == "us-east-1":
                c.create_bucket(Bucket=bname)
            else:
                c.create_bucket(Bucket=bname, CreateBucketConfiguration={"LocationConstraint": config.aws_region})
            return _ok({"bucket": bname, "created": True})

        elif name == "delete_s3_bucket":
            bname = args.get("name")
            if not bname:
                return _err("Se requiere 'name'")
            c = _make_client("s3")
            if args.get("force"):
                paginator = c.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bname):
                    objects = page.get("Contents", [])
                    if objects:
                        c.delete_objects(Bucket=bname, Delete={"Objects": [{"Key": o["Key"]} for o in objects]})
            c.delete_bucket(Bucket=bname)
            return _ok({"deleted": bname})

        elif name == "list_s3_objects":
            bname = args.get("bucket")
            if not bname:
                return _err("Se requiere 'bucket'")
            c = _make_client("s3")
            params = {"Bucket": bname, "MaxKeys": args.get("maxKeys", 100)}
            if "prefix" in args:
                params["Prefix"] = args["prefix"]
            r = c.list_objects_v2(**params)
            objects = [{"key": o["Key"], "size": o["Size"], "lastModified": o["LastModified"]} for o in r.get("Contents", [])]
            return _ok({"bucket": bname, "count": len(objects), "objects": objects})

        elif name == "put_s3_object":
            bname = args.get("bucket")
            key = args.get("key")
            content = args.get("content")
            if not bname or not key or content is None:
                return _err("Se requieren 'bucket', 'key' y 'content'")
            c = _make_client("s3")
            c.put_object(
                Bucket=bname,
                Key=key,
                Body=content.encode() if isinstance(content, str) else content,
                ContentType=args.get("contentType", "text/plain"),
            )
            return _ok({"bucket": bname, "key": key, "uploaded": True})

        elif name == "get_s3_object":
            bname = args.get("bucket")
            key = args.get("key")
            if not bname or not key:
                return _err("Se requieren 'bucket' y 'key'")
            c = _make_client("s3")
            r = c.get_object(Bucket=bname, Key=key)
            content = r["Body"].read().decode("utf-8", errors="replace")
            return _ok({"bucket": bname, "key": key, "contentType": r.get("ContentType"), "content": content})

        elif name == "delete_s3_object":
            bname = args.get("bucket")
            key = args.get("key")
            if not bname or not key:
                return _err("Se requieren 'bucket' y 'key'")
            c = _make_client("s3")
            c.delete_object(Bucket=bname, Key=key)
            return _ok({"deleted": f"s3://{bname}/{key}"})

        elif name == "generate_s3_presigned_url":
            bname = args.get("bucket")
            key = args.get("key")
            if not bname or not key:
                return _err("Se requieren 'bucket' y 'key'")
            c = _make_client("s3")
            url = c.generate_presigned_url(
                ClientMethod=args.get("operation", "get_object"),
                Params={"Bucket": bname, "Key": key},
                ExpiresIn=args.get("expiresIn", 3600),
            )
            return _ok({"url": url, "expiresIn": args.get("expiresIn", 3600)})

        # ── DynamoDB ──────────────────────────────────────────────────────────
        elif name == "list_dynamodb_tables":
            c = _make_client("dynamodb")
            r = c.list_tables()
            return _ok({"tables": r.get("TableNames", [])})

        elif name == "create_dynamodb_table":
            tname = args.get("name")
            pk = args.get("partitionKey")
            if not tname or not pk:
                return _err("Se requieren 'name' y 'partitionKey'")
            pk_type = args.get("partitionKeyType", "S")
            attr_defs = [{"AttributeName": pk, "AttributeType": pk_type}]
            key_schema = [{"AttributeName": pk, "KeyType": "HASH"}]
            if sk := args.get("sortKey"):
                sk_type = args.get("sortKeyType", "S")
                attr_defs.append({"AttributeName": sk, "AttributeType": sk_type})
                key_schema.append({"AttributeName": sk, "KeyType": "RANGE"})
            billing = args.get("billingMode", "PAY_PER_REQUEST")
            params = {
                "TableName": tname,
                "AttributeDefinitions": attr_defs,
                "KeySchema": key_schema,
                "BillingMode": billing,
            }
            if billing == "PROVISIONED":
                params["ProvisionedThroughput"] = {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
            c = _make_client("dynamodb")
            r = c.create_table(**params)
            return _ok({"tableName": tname, "status": r["TableDescription"]["TableStatus"]})

        elif name == "delete_dynamodb_table":
            tname = args.get("name")
            if not tname:
                return _err("Se requiere 'name'")
            c = _make_client("dynamodb")
            c.delete_table(TableName=tname)
            return _ok({"deleted": tname})

        elif name == "put_dynamodb_item":
            tname = args.get("table")
            item = args.get("item")
            if not tname or not item:
                return _err("Se requieren 'table' e 'item'")
            c = _make_client("dynamodb")
            c.put_item(TableName=tname, Item=item)
            return _ok({"table": tname, "inserted": True})

        elif name == "get_dynamodb_item":
            tname = args.get("table")
            key = args.get("key")
            if not tname or not key:
                return _err("Se requieren 'table' y 'key'")
            c = _make_client("dynamodb")
            r = c.get_item(TableName=tname, Key=key)
            return _ok({"item": r.get("Item")})

        elif name == "query_dynamodb":
            tname = args.get("table")
            kce = args.get("keyConditionExpression")
            eav = args.get("expressionAttributeValues")
            if not tname or not kce or not eav:
                return _err("Se requieren 'table', 'keyConditionExpression' y 'expressionAttributeValues'")
            c = _make_client("dynamodb")
            params = {"TableName": tname, "KeyConditionExpression": kce, "ExpressionAttributeValues": eav}
            if "filterExpression" in args:
                params["FilterExpression"] = args["filterExpression"]
            if "limit" in args:
                params["Limit"] = args["limit"]
            if "scanIndexForward" in args:
                params["ScanIndexForward"] = args["scanIndexForward"]
            r = c.query(**params)
            return _ok({"count": r.get("Count", 0), "items": r.get("Items", [])})

        elif name == "scan_dynamodb":
            tname = args.get("table")
            if not tname:
                return _err("Se requiere 'table'")
            c = _make_client("dynamodb")
            params = {"TableName": tname}
            if "filterExpression" in args:
                params["FilterExpression"] = args["filterExpression"]
            if "expressionAttributeValues" in args:
                params["ExpressionAttributeValues"] = args["expressionAttributeValues"]
            if "limit" in args:
                params["Limit"] = args["limit"]
            r = c.scan(**params)
            return _ok({"count": r.get("Count", 0), "items": r.get("Items", [])})

        elif name == "delete_dynamodb_item":
            tname = args.get("table")
            key = args.get("key")
            if not tname or not key:
                return _err("Se requieren 'table' y 'key'")
            c = _make_client("dynamodb")
            c.delete_item(TableName=tname, Key=key)
            return _ok({"deleted": True})

        # ── Secrets Manager ───────────────────────────────────────────────────
        elif name == "list_secrets":
            c = _make_client("secretsmanager")
            r = c.list_secrets()
            return _ok({"secrets": [{"name": s["Name"], "arn": s["ARN"], "description": s.get("Description", "")} for s in r.get("SecretList", [])]})

        elif name == "create_secret":
            sname = args.get("name")
            value = args.get("value")
            if not sname or value is None:
                return _err("Se requieren 'name' y 'value'")
            c = _make_client("secretsmanager")
            params = {"Name": sname, "SecretString": value}
            if "description" in args:
                params["Description"] = args["description"]
            r = c.create_secret(**params)
            return _ok({"arn": r["ARN"], "name": r["Name"]})

        elif name == "get_secret_value":
            name_or_arn = args.get("nameOrArn")
            if not name_or_arn:
                return _err("Se requiere 'nameOrArn'")
            c = _make_client("secretsmanager")
            r = c.get_secret_value(SecretId=name_or_arn)
            return _ok({"name": r["Name"], "arn": r["ARN"], "value": r.get("SecretString")})

        elif name == "update_secret":
            name_or_arn = args.get("nameOrArn")
            value = args.get("value")
            if not name_or_arn or value is None:
                return _err("Se requieren 'nameOrArn' y 'value'")
            c = _make_client("secretsmanager")
            r = c.update_secret(SecretId=name_or_arn, SecretString=value)
            return _ok({"arn": r["ARN"], "updated": True})

        elif name == "delete_secret":
            name_or_arn = args.get("nameOrArn")
            if not name_or_arn:
                return _err("Se requiere 'nameOrArn'")
            c = _make_client("secretsmanager")
            params = {"SecretId": name_or_arn}
            if args.get("force"):
                params["ForceDeleteWithoutRecovery"] = True
            c.delete_secret(**params)
            return _ok({"deleted": name_or_arn})

        # ── KMS ───────────────────────────────────────────────────────────────
        elif name == "list_kms_keys":
            c = _make_client("kms")
            keys_resp = c.list_keys()
            aliases_resp = c.list_aliases()
            alias_map = {a.get("TargetKeyId"): a.get("AliasName") for a in aliases_resp.get("Aliases", []) if a.get("TargetKeyId")}
            result = [{"keyId": k["KeyId"], "arn": k["KeyArn"], "alias": alias_map.get(k["KeyId"])} for k in keys_resp.get("Keys", [])]
            return _ok({"keys": result})

        elif name == "create_kms_key":
            c = _make_client("kms")
            params = {}
            if "description" in args:
                params["Description"] = args["description"]
            r = c.create_key(**params)
            key_id = r["KeyMetadata"]["KeyId"]
            alias = args.get("alias")
            if alias:
                if not alias.startswith("alias/"):
                    alias = f"alias/{alias}"
                c.create_alias(AliasName=alias, TargetKeyId=key_id)
            return _ok({"keyId": key_id, "arn": r["KeyMetadata"]["Arn"], "alias": alias})

        elif name == "kms_encrypt":
            key_id = args.get("keyId")
            plaintext = args.get("plaintext")
            if not key_id or plaintext is None:
                return _err("Se requieren 'keyId' y 'plaintext'")
            c = _make_client("kms")
            r = c.encrypt(KeyId=key_id, Plaintext=plaintext.encode())
            return _ok({"ciphertextBlob": base64.b64encode(r["CiphertextBlob"]).decode(), "keyId": r["KeyId"]})

        elif name == "kms_decrypt":
            blob = args.get("ciphertextBlob")
            if not blob:
                return _err("Se requiere 'ciphertextBlob'")
            c = _make_client("kms")
            r = c.decrypt(CiphertextBlob=base64.b64decode(blob))
            return _ok({"plaintext": r["Plaintext"].decode(), "keyId": r["KeyId"]})

        # ── EventBridge ───────────────────────────────────────────────────────
        elif name == "list_eventbridge_buses":
            c = _make_client("events")
            r = c.list_event_buses()
            return _ok({"buses": [{"name": b["Name"], "arn": b["Arn"]} for b in r.get("EventBuses", [])]})

        elif name == "put_eventbridge_events":
            entries = args.get("entries")
            if not entries:
                return _err("Se requiere 'entries'")
            c = _make_client("events")
            r = c.put_events(Entries=entries)
            return _ok({"failedEntryCount": r["FailedEntryCount"], "entries": r.get("Entries", [])})

        elif name == "list_eventbridge_rules":
            c = _make_client("events")
            params = {"EventBusName": args.get("busName", "default")}
            r = c.list_rules(**params)
            return _ok({"rules": r.get("Rules", [])})

        elif name == "create_eventbridge_rule":
            rname = args.get("name")
            if not rname:
                return _err("Se requiere 'name'")
            c = _make_client("events")
            bus = args.get("busName", "default")
            params = {"Name": rname, "EventBusName": bus, "State": "ENABLED"}
            if "scheduleExpression" in args:
                params["ScheduleExpression"] = args["scheduleExpression"]
            elif "eventPattern" in args:
                params["EventPattern"] = args["eventPattern"] if isinstance(args["eventPattern"], str) else json.dumps(args["eventPattern"])
            r = c.put_rule(**params)
            result = {"ruleArn": r["RuleArn"]}
            if targets := args.get("targets"):
                c.put_targets(Rule=rname, EventBusName=bus, Targets=targets)
                result["targets"] = targets
            return _ok(result)

        elif name == "delete_eventbridge_rule":
            rname = args.get("name")
            if not rname:
                return _err("Se requiere 'name'")
            c = _make_client("events")
            bus = args.get("busName", "default")
            try:
                targets_resp = c.list_targets_by_rule(Rule=rname, EventBusName=bus)
                if target_ids := [t["Id"] for t in targets_resp.get("Targets", [])]:
                    c.remove_targets(Rule=rname, EventBusName=bus, Ids=target_ids)
            except Exception:
                pass
            c.delete_rule(Name=rname, EventBusName=bus)
            return _ok({"deleted": rname})

        # ── Step Functions ────────────────────────────────────────────────────
        elif name == "list_step_functions":
            c = _make_client("stepfunctions")
            r = c.list_state_machines()
            return _ok({"stateMachines": r.get("stateMachines", [])})

        elif name == "start_sfn_execution":
            sm_arn = args.get("stateMachineArn")
            if not sm_arn:
                return _err("Se requiere 'stateMachineArn'")
            c = _make_client("stepfunctions")
            params = {"stateMachineArn": sm_arn, "input": json.dumps(args.get("input", {}))}
            if "name" in args:
                params["name"] = args["name"]
            r = c.start_execution(**params)
            return _ok({"executionArn": r["executionArn"], "startDate": r["startDate"]})

        elif name == "describe_sfn_execution":
            exec_arn = args.get("executionArn")
            if not exec_arn:
                return _err("Se requiere 'executionArn'")
            c = _make_client("stepfunctions")
            r = c.describe_execution(executionArn=exec_arn)
            return _ok({
                "executionArn": r["executionArn"],
                "status": r["status"],
                "startDate": r["startDate"],
                "stopDate": r.get("stopDate"),
                "input": r.get("input"),
                "output": r.get("output"),
            })

        elif name == "list_sfn_executions":
            sm_arn = args.get("stateMachineArn")
            if not sm_arn:
                return _err("Se requiere 'stateMachineArn'")
            c = _make_client("stepfunctions")
            params = {"stateMachineArn": sm_arn, "maxResults": args.get("maxResults", 20)}
            if "statusFilter" in args:
                params["statusFilter"] = args["statusFilter"]
            r = c.list_executions(**params)
            return _ok({"executions": r.get("executions", [])})

        # ── Athena ────────────────────────────────────────────────────────────
        elif name == "list_glue_databases":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/athena/catalog"))]

        elif name == "run_athena_query":
            sql = args.get("sql")
            if not sql:
                return _err("Se requiere 'sql'")
            payload = {
                "query": sql,
                "database": args.get("database", "default"),
                "workGroup": args.get("workgroup", "primary"),
            }
            start_resp = json.loads(await _backend("POST", "/api/athena/query", json_data=payload))
            exec_id = start_resp.get("executionId")
            if not exec_id:
                return [types.TextContent(type="text", text=json.dumps(start_resp, indent=2))]

            timeout = args.get("timeoutSeconds", 30)
            elapsed = 0
            while elapsed < timeout:
                await asyncio.sleep(1)
                elapsed += 1
                status_resp = json.loads(await _backend("GET", f"/api/athena/query/{exec_id}"))
                status = status_resp.get("status")
                if status == "SUCCEEDED":
                    results = await _backend("GET", f"/api/athena/query/{exec_id}/results")
                    return [types.TextContent(type="text", text=results)]
                if status in ("FAILED", "CANCELLED"):
                    return _ok({"status": status, "reason": status_resp.get("stateChangeReason")})

            return _ok({"status": "TIMEOUT", "executionId": exec_id, "message": f"Consulta no completó en {timeout}s"})

        elif name == "get_athena_query_history":
            return [types.TextContent(type="text", text=await _backend("GET", "/api/athena/history"))]

        # ── SES ───────────────────────────────────────────────────────────────
        elif name == "list_ses_identities":
            c = _make_client("ses")
            r = c.list_identities()
            return _ok({"identities": r.get("Identities", [])})

        elif name == "verify_ses_email":
            email = args.get("email")
            if not email:
                return _err("Se requiere 'email'")
            c = _make_client("ses")
            c.verify_email_identity(EmailAddress=email)
            return _ok({"email": email, "verificationInitiated": True})

        elif name == "send_ses_email":
            from_addr = args.get("fromAddress")
            to_addrs = args.get("toAddresses")
            subject = args.get("subject")
            body_text = args.get("bodyText")
            if not all([from_addr, to_addrs, subject, body_text]):
                return _err("Se requieren 'fromAddress', 'toAddresses', 'subject' y 'bodyText'")
            c = _make_client("ses")
            body = {"Text": {"Data": body_text, "Charset": "UTF-8"}}
            if html := args.get("bodyHtml"):
                body["Html"] = {"Data": html, "Charset": "UTF-8"}
            dest = {"ToAddresses": to_addrs}
            if cc := args.get("ccAddresses"):
                dest["CcAddresses"] = cc
            r = c.send_email(
                Source=from_addr,
                Destination=dest,
                Message={"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": body},
            )
            return _ok({"messageId": r["MessageId"]})

        elif name == "get_ses_send_quota":
            c = _make_client("ses")
            r = c.get_send_quota()
            return _ok({
                "max24HourSend": r.get("Max24HourSend"),
                "maxSendRate": r.get("MaxSendRate"),
                "sentLast24Hours": r.get("SentLast24Hours"),
            })

        else:
            return _err(f"Herramienta desconocida: '{name}'")

    except Exception as error:
        return _err(str(error))


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="floci-mcp",
                server_version="0.2.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
