"""Hybrid development: cloud proxying, cloud seeding and tunnels (Area 5).

These capabilities connect the local environment with real AWS resources or with
the internet. They require real credentials (for proxy/seed) or a tunnel binary
(`cloudflared`/`ngrok`) installed on the host. When prerequisites are missing, the
methods degrade with a clear message instead of failing opaquely.
"""
import asyncio
import json
import re
import shutil
from typing import Any, Dict, List, Optional

from floci_backend.application.data_seeder import DataSeeder
from floci_backend.infrastructure.boto_factory import make_client


class HybridService:
    def __init__(self, data_seeder: Optional[DataSeeder] = None):
        self._seeder = data_seeder or DataSeeder()
        self._tunnels: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------- cloud seeding
    def _anonymize_value(self, key: str, value: Any) -> Any:
        from faker import Faker
        fake = Faker()
        lk = key.lower()
        if not isinstance(value, str):
            return value
        if "email" in lk:
            return fake.email()
        if "name" in lk:
            return fake.name()
        if "phone" in lk:
            return fake.phone_number()
        if "address" in lk or "street" in lk or "city" in lk:
            return fake.address().replace("\n", ", ")
        if "@" in value:
            return fake.email()
        return value

    async def seed_from_cloud_dynamodb(
        self,
        source_table: str,
        target_table: Optional[str] = None,
        limit: int = 25,
        anonymize_fields: Optional[List[str]] = None,
        region: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract a subset of a REAL DynamoDB table, anonymize it and inject it
        into the local emulator table."""
        target_table = target_table or source_table
        cloud = make_client(
            "dynamodb",
            endpoint_url="",  # force real AWS
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        try:
            resp = cloud.scan(TableName=source_table, Limit=min(limit, 100))
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "message": f"Could not read the real table: {e}"}

        anonymize_fields = anonymize_fields or []
        records: List[Dict[str, Any]] = []
        for item in resp.get("Items", []):
            record: Dict[str, Any] = {}
            for k, type_val in item.items():
                # type_val is {'S': '...'} / {'N': '...'} / {'BOOL': ...}
                ((_t, v),) = type_val.items()
                if _t == "N":
                    v = float(v) if "." in str(v) else int(v)
                if anonymize_fields and k in anonymize_fields:
                    v = self._anonymize_value(k, v)
                elif not anonymize_fields:
                    v = self._anonymize_value(k, v)
                record[k] = v
            records.append(record)

        await self._seeder.seed_dynamodb(target_table, records)
        return {
            "status": "success",
            "sourceTable": source_table,
            "targetTable": target_table,
            "imported": len(records),
            "anonymized": anonymize_fields or "auto",
        }

    # ------------------------------------------------------- cloud proxying
    async def proxy_cloud_sqs(
        self,
        source_queue_url: str,
        target_type: str,
        target: str,
        max_messages: int = 10,
        delete_after: bool = True,
        region: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Drain messages from a REAL SQS queue (e.g. staging) and forward them to a
        local resource (Lambda/SQS/SNS). One-shot drain of up to `max_messages`."""
        if target_type not in ("lambda", "sqs", "sns"):
            return {"status": "error", "message": "target_type must be lambda, sqs or sns"}

        cloud_sqs = make_client(
            "sqs",
            endpoint_url="",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        try:
            resp = cloud_sqs.receive_message(
                QueueUrl=source_queue_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=2,
            )
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "message": f"Could not read the real queue: {e}"}

        messages = resp.get("Messages", [])
        forwarded = 0
        for msg in messages:
            body = msg["Body"]
            if target_type == "lambda":
                make_client("lambda").invoke(FunctionName=target, Payload=body.encode())
            elif target_type == "sqs":
                make_client("sqs").send_message(QueueUrl=target, MessageBody=body)
            else:
                make_client("sns").publish(TopicArn=target, Message=body)
            forwarded += 1
            if delete_after:
                cloud_sqs.delete_message(
                    QueueUrl=source_queue_url, ReceiptHandle=msg["ReceiptHandle"]
                )

        return {
            "status": "success",
            "source": source_queue_url,
            "target": f"{target_type}:{target}",
            "forwarded": forwarded,
        }

    # ----------------------------------------------------- reverse tunnels
    def _detect_tunnel_binary(self) -> Optional[str]:
        for binary in ("cloudflared", "ngrok"):
            if shutil.which(binary):
                return binary
        return None

    async def start_tunnel(self, port: int = 4566) -> Dict[str, Any]:
        """Expose a local port to the internet via cloudflared/ngrok if installed."""
        binary = self._detect_tunnel_binary()
        if not binary:
            return {
                "status": "unavailable",
                "message": "Install 'cloudflared' or 'ngrok' on the host to open reverse tunnels.",
                "hint": "brew install cloudflared  |  https://ngrok.com/download",
            }

        if binary == "cloudflared":
            args = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]
            url_re = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
        else:
            args = ["ngrok", "http", str(port), "--log", "stdout"]
            url_re = re.compile(r"https://[a-z0-9-]+\.ngrok[a-z0-9.-]*\.(?:io|app|dev)")

        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )

        public_url: Optional[str] = None
        try:
            for _ in range(40):  # ~20s scanning the output for the URL
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=0.5)
                if not line:
                    if proc.returncode is not None:
                        break
                    continue
                match = url_re.search(line.decode("utf-8", "replace"))
                if match:
                    public_url = match.group(0)
                    break
        except asyncio.TimeoutError:
            pass

        self._tunnels[str(proc.pid)] = {"pid": proc.pid, "port": port, "url": public_url, "binary": binary, "_proc": proc}
        return {
            "status": "started" if public_url else "starting",
            "pid": proc.pid,
            "port": port,
            "url": public_url,
            "binary": binary,
        }

    def list_tunnels(self) -> List[Dict[str, Any]]:
        return [
            {k: v for k, v in t.items() if k != "_proc"}
            for t in self._tunnels.values()
        ]

    def stop_tunnel(self, pid: str) -> Dict[str, Any]:
        tunnel = self._tunnels.pop(str(pid), None)
        if not tunnel:
            return {"status": "not_found", "pid": pid}
        proc = tunnel.get("_proc")
        if proc and proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        return {"status": "stopped", "pid": pid}
