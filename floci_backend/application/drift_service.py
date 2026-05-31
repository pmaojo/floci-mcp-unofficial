"""Detección de drift y auto-descubrimiento de IaC (Área 4).

Lee el estado de infraestructura como código local (terraform.tfstate o un
listado de recursos de Serverless/CDK exportado a JSON) y lo compara con el
estado real del emulador para detectar:

  - missing:   declarado en IaC pero ausente en el emulador.
  - unmanaged: existe en el emulador pero NO está en el código (drift manual).
  - managed:   presente en ambos lados (en sincronía).
"""
import glob
import json
import os
from typing import Any, Dict, List, Set, Tuple

from floci_backend.infrastructure.boto_factory import make_client

# Mapea tipos de recurso Terraform -> (categoría floci, atributo con el nombre)
TF_TYPE_MAP = {
    "aws_s3_bucket": ("s3", "bucket"),
    "aws_sqs_queue": ("sqs", "name"),
    "aws_dynamodb_table": ("dynamodb", "name"),
    "aws_lambda_function": ("lambda", "function_name"),
    "aws_kms_key": ("kms", "key_id"),
    "aws_sns_topic": ("sns", "name"),
}


class DriftService:
    # ---------------------------------------------------------------- discovery
    def discover(self, path: str = ".") -> Dict[str, Any]:
        """Auto-descubre archivos de IaC en `path` y extrae los recursos declarados."""
        desired, sources = self._read_desired(path)
        grouped: Dict[str, List[str]] = {}
        for category, name in sorted(desired):
            grouped.setdefault(category, []).append(name)
        return {"sources": sources, "resources": grouped, "count": len(desired)}

    def _read_desired(self, path: str) -> Tuple[Set[Tuple[str, str]], List[str]]:
        desired: Set[Tuple[str, str]] = set()
        sources: List[str] = []

        candidates: List[str] = []
        if os.path.isfile(path):
            candidates = [path]
        else:
            candidates += glob.glob(os.path.join(path, "**", "terraform.tfstate"), recursive=True)
            candidates += glob.glob(os.path.join(path, "**", "*.tfstate"), recursive=True)
            candidates += glob.glob(os.path.join(path, "**", "floci-resources.json"), recursive=True)

        for file_path in sorted(set(candidates)):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            found = self._parse_tfstate(data) or self._parse_generic(data)
            if found:
                sources.append(file_path)
                desired |= found

        return desired, sources

    def _parse_tfstate(self, data: Any) -> Set[Tuple[str, str]]:
        out: Set[Tuple[str, str]] = set()
        if not isinstance(data, dict) or "resources" not in data:
            return out
        for res in data.get("resources", []):
            tf_type = res.get("type")
            mapped = TF_TYPE_MAP.get(tf_type)
            if not mapped:
                continue
            category, name_attr = mapped
            for instance in res.get("instances", []):
                attrs = instance.get("attributes", {})
                name = attrs.get(name_attr) or attrs.get("name") or attrs.get("id")
                if name:
                    out.add((category, str(name)))
        return out

    def _parse_generic(self, data: Any) -> Set[Tuple[str, str]]:
        """Soporta un JSON exportado de Serverless/CDK: [{type, name}, ...]."""
        out: Set[Tuple[str, str]] = set()
        items = data if isinstance(data, list) else data.get("resources", []) if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict) and item.get("type") and item.get("name"):
                out.add((str(item["type"]), str(item["name"])))
        return out

    # ------------------------------------------------------------------- actual
    def _read_actual(self) -> Set[Tuple[str, str]]:
        actual: Set[Tuple[str, str]] = set()
        try:
            for b in make_client("s3").list_buckets().get("Buckets", []):
                actual.add(("s3", b["Name"]))
        except Exception:
            pass
        try:
            for url in make_client("sqs").list_queues().get("QueueUrls", []):
                actual.add(("sqs", url.split("/")[-1]))
        except Exception:
            pass
        try:
            for t in make_client("dynamodb").list_tables().get("TableNames", []):
                actual.add(("dynamodb", t))
        except Exception:
            pass
        try:
            for fn in make_client("lambda").list_functions().get("Functions", []):
                actual.add(("lambda", fn["FunctionName"]))
        except Exception:
            pass
        try:
            for topic in make_client("sns").list_topics().get("Topics", []):
                actual.add(("sns", topic["TopicArn"].split(":")[-1]))
        except Exception:
            pass
        return actual

    # -------------------------------------------------------------------- drift
    def detect_drift(self, path: str = ".") -> Dict[str, Any]:
        desired, sources = self._read_desired(path)
        actual = self._read_actual()

        # KMS no se compara por nombre (los key_id son UUIDs generados), se ignora
        desired = {(c, n) for (c, n) in desired if c != "kms"}

        missing = sorted(desired - actual)
        unmanaged = sorted(actual - desired)
        managed = sorted(desired & actual)

        def fmt(items: List[Tuple[str, str]]) -> List[Dict[str, str]]:
            return [{"category": c, "name": n} for c, n in items]

        return {
            "sources": sources,
            "inSync": len(missing) == 0 and len(unmanaged) == 0,
            "summary": {
                "managed": len(managed),
                "missing": len(missing),
                "unmanaged": len(unmanaged),
            },
            "missing": fmt(missing),
            "unmanaged": fmt(unmanaged),
            "managed": fmt(managed),
        }
