from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import jwt
import httpx
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import docker
import logging
from floci_backend.infrastructure.aws_cli import AwsCli
import json

logger = logging.getLogger(__name__)

router = APIRouter()

class JwtRequest(BaseModel):
    claims: Dict[str, Any]
    secret: str
    algorithm: str = "HS256"

@router.post("/studio/auth/generate-token")
async def generate_token(request: JwtRequest):
    try:
        token = jwt.encode(request.claims, request.secret, algorithm=request.algorithm)
        return {"token": token}
    except Exception as e:
        logger.warning("Token generation failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid token generation request")

class ProxyRequest(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None

@router.post("/studio/client/proxy")
async def proxy_request(request: ProxyRequest):
    import time
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        try:
            kwargs = {
                "method": request.method,
                "url": request.url,
                "headers": request.headers or {},
            }
            if request.body is not None:
                if isinstance(request.body, (dict, list)):
                    kwargs["json"] = request.body
                else:
                    kwargs["content"] = str(request.body)

            response = await client.request(**kwargs)
            latency_ms = int((time.time() - start_time) * 1000)

            response_body = response.text
            try:
                response_json = response.json()
                response_body = response_json
            except Exception:
                pass

            return {
                "status": response.status_code,
                "headers": dict(response.headers),
                "body": response_body,
                "latency_ms": latency_ms
            }
        except Exception as e:
            logger.exception("Proxy request failed")
            raise HTTPException(status_code=500, detail="Proxy request failed")

@router.get("/studio/architecture")
async def get_architecture():
    aws_cli = AwsCli()
    nodes = []
    edges = []
    node_id_counter = 1

    def add_node(label, type_name):
        nonlocal node_id_counter
        node_id = f"node_{node_id_counter}"
        node_id_counter += 1
        nodes.append({"id": node_id, "label": label, "type": type_name})
        return node_id

    try:
        s3_client = aws_cli.get_client("s3")
        buckets = s3_client.list_buckets().get("Buckets", [])
        for b in buckets:
            add_node(b["Name"], "S3")

        sqs_client = aws_cli.get_client("sqs")
        queues = sqs_client.list_queues().get("QueueUrls", [])
        for q_url in queues:
            q_name = q_url.split("/")[-1]
            add_node(q_name, "SQS")

        dynamo_client = aws_cli.get_client("dynamodb")
        tables = dynamo_client.list_tables().get("TableNames", [])
        for t in tables:
            add_node(t, "DynamoDB")

        lambda_client = aws_cli.get_client("lambda")
        functions = lambda_client.list_functions().get("Functions", [])
        for f in functions:
            add_node(f["FunctionName"], "Lambda")

        apigw_client = aws_cli.get_client("apigateway")
        apis = apigw_client.get_rest_apis().get("items", [])
        for api in apis:
            add_node(api["name"], "ApiGateway")

        kms_client = aws_cli.get_client("kms")
        keys = kms_client.list_keys().get("Keys", [])
        for k in keys:
            add_node(k["KeyId"], "KMS")

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        logger.exception("Failed to fetch architecture")
        raise HTTPException(status_code=500, detail="Failed to fetch architecture data")

@router.websocket("/studio/lambda-logs/ws")
async def websocket_lambda_logs(websocket: WebSocket):
    await websocket.accept()

    try:
        client = docker.from_env()
        containers = client.containers.list()
        # Find floci container or localstack
        target_container = None
        for c in containers:
            if "floci" in c.name.lower() or "localstack" in c.name.lower():
                target_container = c
                break

        if not target_container:
            await websocket.send_text(json.dumps({"type": "info", "message": "No Floci container found. Stream will wait."}))

        async def stream_logs():
            if not target_container:
                return

            # Using asyncio to read logs without blocking
            # This is a simplification; ideally we use an async docker client
            # But for standard docker-py, we run generator in a thread
            def get_logs():
                return target_container.logs(stream=True, tail=100)

            loop = asyncio.get_event_loop()
            logs_stream = await loop.run_in_executor(None, get_logs)

            for line in logs_stream:
                try:
                    await websocket.send_text(json.dumps({
                        "type": "log",
                        "content": line.decode("utf-8", errors="replace").strip()
                    }))
                except Exception:
                    break

        stream_task = asyncio.create_task(stream_logs())

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
