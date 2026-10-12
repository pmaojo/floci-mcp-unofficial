FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

# Evitar escritura de bytecodes en disco y habilitar enlace optimizado de uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Instalar dependencias en una capa estable independiente
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-install-project --no-dev

# Copiar el código del servidor
COPY floci_mcp.py toolsets.py decider.py skills_catalog.py ./
COPY tools/ ./tools/
COPY floci_generic/ ./floci_generic/
COPY plugins/ ./plugins/
COPY recipes/ ./recipes/
COPY floci_backend/ ./floci_backend/
RUN uv sync --no-dev

# Capa de ejecucion limpia
FROM python:3.12-alpine

# run_local_aws_cmd, the Glue catalog and Lambda deployment call the aws CLI;
# the marketplace tools call docker compose (mount the host socket to use them).
RUN apk add --no-cache aws-cli docker-cli docker-cli-compose

WORKDIR /app

# Copiar entorno virtual y app compilada
COPY --from=builder /app /app

# Configurar variables de entorno por defecto
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SIDECAR_URL="http://host.docker.internal:4317" \
    AWS_ENDPOINT_URL="http://host.docker.internal:4566" \
    FLOCI_AZURE_ENDPOINT="http://host.docker.internal:4577" \
    FLOCI_GCP_ENDPOINT="http://host.docker.internal:4588" \
    FLOCI_OCI_ENDPOINT="http://host.docker.internal:4599" \
    SIDECAR_TOKEN="open"

# Correr el servidor a traves de stdio interactivo
CMD ["python", "floci_mcp.py"]
