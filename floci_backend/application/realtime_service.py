"""WebSocket real-time broadcast service with background resource polling."""
import asyncio
import json
from typing import Any, Dict, Set

from fastapi import WebSocket

from floci_backend.infrastructure.aws_cli import AwsCli


_POLL_INTERVAL = 10  # seconds between resource snapshots


class RealtimeService:
    def __init__(self, aws_cli: AwsCli):
        self._aws_cli = aws_cli
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._poll_loop())

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, msg: Dict[str, Any]) -> None:
        text = json.dumps(msg)
        dead: Set[WebSocket] = set()
        async with self._lock:
            clients = set(self._clients)
        for ws in clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                self._clients -= dead

    async def push_marketplace_status(self, recipe_id: str, status: str) -> None:
        await self.broadcast({"type": "marketplace_status", "payload": {"recipeId": recipe_id, "status": status}})

    async def _poll_loop(self) -> None:
        while True:
            async with self._lock:
                if not self._clients:
                    self._task = None
                    return
            try:
                snapshot = await self._collect_counts()
                await self.broadcast({"type": "resource_snapshot", "payload": snapshot})
            except Exception:
                pass
            await asyncio.sleep(_POLL_INTERVAL)

    async def _count(self, args: list[str], key: str) -> int:
        try:
            result = await self._aws_cli.run_json(args)
            val = result.get(key, [])
            return len(val) if isinstance(val, list) else 0
        except Exception:
            return -1

    async def _collect_counts(self) -> Dict[str, int]:
        counts = await asyncio.gather(
            self._count(["s3", "list-buckets"], "Buckets"),
            self._count(["dynamodb", "list-tables"], "TableNames"),
            self._count(["lambda", "list-functions"], "Functions"),
            self._count(["sqs", "list-queues"], "QueueUrls"),
            self._count(["sns", "list-topics"], "Topics"),
            self._count(["secretsmanager", "list-secrets"], "SecretList"),
            self._count(["kms", "list-keys"], "Keys"),
            self._count(["events", "list-rules"], "Rules"),
            return_exceptions=False,
        )
        keys = ["s3", "dynamodb", "lambda", "sqs", "sns", "secrets", "kms", "eventbridge"]
        return dict(zip(keys, counts))
