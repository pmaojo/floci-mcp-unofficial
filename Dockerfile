FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

# Evitar escritura de bytecodes en disco y habilitar enlace optimizado de uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Instalar dependencias en una capa estable independiente
COPY pyproject.toml README.md ./
RUN uv sync --no-install-project --no-dev

# Copiar el código del servidor
COPY floci_mcp.py ./
RUN uv sync --no-dev

# Capa de ejecucion limpia
FROM python:3.12-alpine

WORKDIR /app

# Copiar entorno virtual y app compilada
COPY --from=builder /app /app

# Configurar variables de entorno por defecto
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SIDECAR_URL="http://host.docker.internal:4317" \
    AWS_ENDPOINT_URL="http://host.docker.internal:4566" \
    SIDECAR_TOKEN="open"

# Correr el servidor a traves de stdio interactivo
CMD ["python", "floci_mcp.py"]
