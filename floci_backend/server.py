from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from floci_backend.config import config, SIDECAR_TOKEN_HEADER

from floci_backend.infrastructure.aws_cli import AwsCli
from floci_backend.application.lambda_service import LambdaService
from floci_backend.application.eks_service import EksService
from floci_backend.application.aws_resource_service import AwsResourceService
from floci_backend.application.compatibility_service import CompatibilityService
from floci_backend.application.recipe_service import RecipeService
from floci_backend.application.diagnostics_service import DiagnosticsService
from floci_backend.application.athena_service import AthenaService

from floci_backend.api.lambda_routes import create_lambda_router
from floci_backend.api.eks_routes import create_eks_router
from floci_backend.api.aws_resource_routes import create_aws_resource_router
from floci_backend.api.diagnostics_routes import create_diagnostics_router
from floci_backend.api.marketplace_routes import create_marketplace_router
from floci_backend.api.athena_routes import create_athena_router
from floci_backend.api.mcp_extensions_routes import create_mcp_extensions_router
from floci_backend.api.studio_routes import router as studio_router
from floci_backend.api.observability_routes import create_observability_router
from floci_backend.api.iac_routes import create_iac_router
from floci_backend.api.hybrid_routes import create_hybrid_router
from floci_backend.api.extensibility_routes import create_extensibility_router

from floci_backend.application.iac_generator import IacGenerator
from floci_backend.application.data_seeder import DataSeeder
from floci_backend.application.topology_mapper import TopologyMapper
from floci_backend.application.flight_recorder import FlightRecorder
from floci_backend.application.drift_service import DriftService
from floci_backend.application.hybrid_service import HybridService
from floci_backend.application.lifecycle_hub import LifecycleHub
from floci_backend.application.plugin_registry import PluginRegistry

# Initialize Services
aws_cli = AwsCli()
iac_generator = IacGenerator()
data_seeder = DataSeeder()
topology_mapper = TopologyMapper()
recipe_service = RecipeService()
compatibility_service = CompatibilityService(recipe_service=recipe_service)
lambda_service = LambdaService(aws_cli=aws_cli)
eks_service = EksService(aws_cli=aws_cli)
aws_resource_service = AwsResourceService(aws_cli=aws_cli, compatibility_service=compatibility_service)
diagnostics_service = DiagnosticsService(aws_cli=aws_cli, compatibility_service=compatibility_service)
athena_service = AthenaService(aws_cli=aws_cli)

# Enterprise-parity services (Áreas 3/4/5/6)
flight_recorder = FlightRecorder()
drift_service = DriftService()
hybrid_service = HybridService(data_seeder=data_seeder)
lifecycle_hub = LifecycleHub()
plugin_registry = PluginRegistry()

app = FastAPI(title="Floci Unified Engine")

origins = config.allowed_origins

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Ensure error payloads return {"error": ...} as expected by the React UI
    # instead of the FastAPI default {"detail": ...}
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", SIDECAR_TOKEN_HEADER],
)

@app.middleware("http")
async def token_middleware(request: Request, call_next):
    if request.url.path == "/health" or request.url.path.startswith("/openapi") or request.url.path.startswith("/docs"):
        return await call_next(request)

    if config.token:
        provided_header = request.headers.get(SIDECAR_TOKEN_HEADER, '').strip()
        auth_header = request.headers.get('authorization', '')

        token_valid = False
        if provided_header == config.token:
            token_valid = True
        elif auth_header.startswith('Bearer ') and auth_header[7:].strip() == config.token:
            token_valid = True

        if not token_valid:
            return JSONResponse(status_code=401, content={"error": "Sidecar token required"})

    try:
        response = await call_next(request)
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/health")
async def health_check():
    return {
        "ok": True,
        "endpointUrl": config.aws_endpoint_url,
        "region": config.aws_region,
        "tokenRequired": bool(config.token)
    }

app.include_router(create_lambda_router(lambda_service), prefix="/api")
app.include_router(create_eks_router(eks_service), prefix="/api")
app.include_router(create_aws_resource_router(aws_resource_service, compatibility_service), prefix="/api")
app.include_router(create_diagnostics_router(diagnostics_service), prefix="/api")
app.include_router(create_marketplace_router(recipe_service), prefix="/api")
app.include_router(create_athena_router(athena_service), prefix="/api")
app.include_router(create_mcp_extensions_router(aws_cli, iac_generator, data_seeder, topology_mapper), prefix="/api")
app.include_router(studio_router, prefix="/api")
app.include_router(create_observability_router(flight_recorder), prefix="/api")
app.include_router(create_iac_router(drift_service), prefix="/api")
app.include_router(create_hybrid_router(hybrid_service), prefix="/api")
app.include_router(create_extensibility_router(lifecycle_hub, plugin_registry), prefix="/api")

# Hace el lifecycle hub accesible desde otros routers (ej. interceptores en el proxy)
app.state.lifecycle_hub = lifecycle_hub
