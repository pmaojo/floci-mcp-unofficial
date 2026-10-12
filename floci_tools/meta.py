"""Health checks, arquitectura y utilidades generales del entorno."""
import httpx
from floci_backend.config import config
from floci_backend.server import app
from floci_tools._client import backend


def register(mcp):

    @mcp.tool()
    async def check_floci_health() -> dict:
        """Checks whether the Floci backend and the AWS emulator are answering. Returns the status of each component."""
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
        """Lists the catalogue of AWS services Floci can manage (S3, Lambda, SQS, SNS, ...) and which ones have resources."""
        return await backend("GET", "/api/aws-services")

    @mcp.tool()
    async def get_service_resources(service_key: str) -> dict:
        """
        Reads the inventory of one AWS service.

        service_key examples: 's3', 'lambda', 'sqs', 'sns', 'dynamodb', 'iam', 'rds'.
        """
        return await backend("GET", f"/api/aws-services/{service_key.lower()}/overview")

    @mcp.tool()
    async def get_architecture_diagram() -> dict:
        """
        Returns a diagram of every active resource in the environment: S3 buckets, SQS queues,
        DynamoDB tables, Lambda functions, APIs and KMS keys.
        """
        return await backend("GET", "/api/studio/architecture")

    @mcp.tool()
    async def get_cost_forecast() -> dict:
        """Estimates the monthly cost on real AWS of the resources deployed in the local environment."""
        return await backend("GET", "/api/diagnostics/cost-forecast")

    @mcp.tool()
    async def get_network_topology() -> dict:
        """Returns the local Docker network map of Floci: containers, networks and exposed ports."""
        return await backend("GET", "/api/extensions/network-topology")

    @mcp.tool()
    async def get_enterprise_roadmap() -> dict:
        """
        Returns the roadmap of planned capabilities to reach parity with enterprise emulators:
        resilience, state management, observability, IaC sync, hybrid development and extensibility.
        """
        return {
            "roadmap": [
                {
                    "title": "1. Resiliencia e Ingeniería del Caos Avanzada",
                    "points": [
                        {"subtitle": "Inyección de latencia granular", "text": "Capacidad de configurar retrasos artificiales por servicio, por endpoint o incluso por porcentaje de peticiones (ej. 'el 10% de las llamadas a S3 tardan 3 segundos') para testear timeouts en las capas de infraestructura hexagonal."},
                        {"subtitle": "Simulación de excepciones nativas (Fault Injection)", "text": "Interfaz para forzar errores específicos de AWS, como un ProvisionedThroughputExceededException en DynamoDB o un 502 Bad Gateway. Esto es fundamental para validar lógicas de recuperación robustas (como las implementaciones del patrón R.A.L.P.H. — Retry And Loop Persistently until Happy) sin tener que desplegar a la nube."},
                        {"subtitle": "Interrupciones de red dirigidas", "text": "Simular caídas de conectividad 'cortando el cable' virtual de un contenedor específico (ej. aislar la base de datos temporalmente) para comprobar cómo el sistema maneja la consistencia eventual y la reconexión."}
                    ]
                },
                {
                    "title": "2. Gestión de Estados y Colaboración de Entornos",
                    "points": [
                        {"subtitle": "Snapshots de estado completo", "text": "Una herramienta para congelar una imagen exacta del emulador en un momento dado (tablas pobladas, mensajes en cola, Lambdas desplegadas, archivos en S3) y volcarla en un archivo comprimido."},
                        {"subtitle": "Cloud Pods locales", "text": "Un sistema de importación/exportación que permita a un desarrollador compartir su entorno exacto con otro compañero para replicar un bug, eliminando la necesidad de correr pesados scripts de seeding manuales."},
                        {"subtitle": "Integración profunda con CI/CD", "text": "Comandos de CLI optimizados para inyectar un estado prefabricado justo antes de ejecutar tests de integración sobre un vertical slice en GitHub Actions o GitLab."}
                    ]
                },
                {
                    "title": "3. Observabilidad, Trazabilidad y Debugging Distribuido",
                    "points": [
                        {"subtitle": "Topología visual estilo X-Ray", "text": "Un mapa interactivo en el cockpit que renderice de forma gráfica la traza completa de un evento asíncrono (ej. el camino de un payload desde API Gateway, pasando por una Lambda, hasta acabar en EventBridge y SQS)."},
                        {"subtitle": "Time-travel debugging", "text": "La capacidad de interceptar un evento en tránsito, pausar su ejecución en el cockpit, inspeccionar/modificar el payload JSON en caliente y reanudar su viaje."},
                        {"subtitle": "Gestión visual de Dead Letter Queues (DLQ)", "text": "Una vista dedicada puramente a monitorizar mensajes fallidos, con botones de un clic para inspeccionar el motivo del fallo y re-encolar (redrive) el mensaje a la cola original tras arreglar el código."}
                    ]
                },
                {
                    "title": "4. Sincronización Bidireccional con Infraestructura como Código (IaC)",
                    "points": [
                        {"subtitle": "Auto-descubrimiento visual", "text": "Capacidad de leer archivos locales como terraform.tfstate, configuraciones de Serverless Framework o plantillas CDK, y dibujar automáticamente el diagrama de los recursos en la interfaz."},
                        {"subtitle": "Generación de código desde la UI", "text": "Permitir que un agente o usuario cree un recurso haciendo clic en el cockpit (ej. crear un bucket S3) y que Floci escriba automáticamente el bloque de código Terraform equivalente en el editor."},
                        {"subtitle": "Detección de Drift local", "text": "Alertas visuales cuando un recurso creado manualmente en el emulador no coincide con lo definido en el repositorio de código de infraestructura."}
                    ]
                },
                {
                    "title": "5. Desarrollo Híbrido, Proxies y Datos Reales",
                    "points": [
                        {"subtitle": "Live Cloud Proxying", "text": "Soporte nativo para enrutar tráfico desde recursos vivos en AWS (como un topic SNS en staging) directamente hacia una función Lambda que el desarrollador está ejecutando en su máquina local, facilitando un bucle de feedback inmediato."},
                        {"subtitle": "Data Seeding desde la nube", "text": "Integración para conectar de forma segura a una base de datos real en AWS, extraer un subconjunto de datos, anonimizarlos al vuelo e inyectarlos en el DynamoDB o RDS emulado localmente."},
                        {"subtitle": "Túneles inversos integrados", "text": "Una función estilo ngrok construida dentro del cockpit para exponer un API Gateway local a internet mediante una URL temporal, útil para probar webhooks de terceros (como Stripe o GitHub)."}
                    ]
                },
                {
                    "title": "6. Extensibilidad, Ecosistema y Hooks Personalizados",
                    "points": [
                        {"subtitle": "SDK de Plugins", "text": "Una API pública y documentada que permita a la comunidad escribir sus propios adaptadores para servicios de AWS menos comunes o herramientas propietarias que el núcleo de Floci no soporta por defecto."},
                        {"subtitle": "Interceptores HTTP programables", "text": "Posibilidad de inyectar middleware personalizado (scripts ligeros) que intercepte y modifique las peticiones/respuestas entre los SDKs de AWS y el motor de emulación local."},
                        {"subtitle": "Webhooks de ciclo de vida", "text": "Eventos disparados por el propio emulador (ej. floci.resource.created) para integrarse con herramientas de notificación u otros agentes de IA del entorno de desarrollo."}
                    ]
                }
            ]
        }
