"""
Floci MCP Server — punto de entrada.

Los tools están organizados por servicio AWS en mcp/tools/:
  meta.py        — health, arquitectura, inventario
  lambda_.py     — funciones serverless
  sqs.py         — colas de mensajes
  sns.py         — notificaciones y pub/sub
  s3.py          — object storage
  dynamodb.py    — base de datos NoSQL
  secrets.py     — Secrets Manager
  kms.py         — cifrado de claves
  eventbridge.py — eventos y reglas
  stepfunctions.py — orquestación de flujos
  athena.py      — consultas SQL analíticas
  ses.py         — envío de emails
  marketplace.py — recetas Docker locales (incl. dynamodb-admin)
  devtools.py    — IaC, seed data, proxy, JWT, tests
  tags.py        — gestión de tags en todos los recursos AWS
"""
from mcp.server.fastmcp import FastMCP
from tools import (
    athena,
    devtools,
    dynamodb,
    eventbridge,
    kms,
    lambda_,
    marketplace,
    meta,
    s3,
    secrets,
    ses,
    sns,
    sqs,
    stepfunctions,
    tags,
)

mcp = FastMCP("floci-mcp")

for module in [
    meta,
    lambda_,
    sqs,
    sns,
    s3,
    dynamodb,
    secrets,
    kms,
    eventbridge,
    stepfunctions,
    athena,
    ses,
    marketplace,
    devtools,
    tags,
]:
    module.register(mcp)

if __name__ == "__main__":
    mcp.run()
