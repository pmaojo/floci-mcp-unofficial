"""Describing an AWS operation from its service model.

`model` is anything shaped like a botocore ServiceModel (operation_names, protocol,
operation_model(name) with input_shape, output_shape, http, documentation). The domain never
imports botocore: the adapter that loads the models is what makes that shape real.
"""
import html
import re
from typing import Any

from floci_generic.domain.classify import Verdict, classify_aws
from floci_generic.domain.clouds import REST_PROTOCOLS

_NOTICE = re.compile(
    r"^(end of support|note:|important:|this (api|operation|action) (is|has been) (deprecated|replaced))"
    r"|^(this change|starting|as of|beginning)", re.I)
_ACTION = re.compile(r"^[A-Z][a-z]+s\b")  # "Adds", "Retrieves", "Invokes": how most operations open


def plain_text(text: str, limit: int = 240) -> str:
    """HTML documentation as one short line of text."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def signature(shape: Any, depth: int = 2) -> str:
    """A compact type. Shapes can be recursive (DynamoDB's AttributeValue), so depth is a hard stop."""
    kind = shape.type_name
    if depth <= 0:
        return "object" if kind == "structure" else kind
    if kind == "structure":
        required = set(shape.required_members)
        inner = ", ".join(f"{n}{'*' if n in required else ''}: {signature(m, depth - 1)}" for n, m in shape.members.items())
        return "{" + inner + "}"
    if kind == "list":
        return f"[{signature(shape.member, depth - 1)}]"
    if kind == "map":
        return f"map<{signature(shape.key, 0)}, {signature(shape.value, depth - 1)}>"
    enum = getattr(shape, "enum", None)
    if enum:
        return "enum(" + "|".join(enum[:8]) + ("|…" if len(enum) > 8 else "") + ")"
    return kind


def summary(documentation: str, limit: int = 200) -> str:
    """First useful sentence of an operation's documentation, skipping notices.

    Notices are whole paragraphs in the HTML, so the paragraph is the unit that is skipped.
    """
    paragraphs = re.findall(r"<p>(.*?)</p>", documentation or "", re.S) or [documentation or ""]
    texts = [t for t in (plain_text(p, 600) for p in paragraphs) if t]
    pick = (next((t for t in texts if _ACTION.match(t) and not _NOTICE.match(t)), None)
            or next((t for t in texts if not _NOTICE.match(t)), None)
            or (texts[0] if texts else ""))
    sentence = re.split(r"(?<=[a-z0-9)])\.\s+(?=[A-Z])", pick)[0]
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rstrip() + "…"


def first_sentence(model: Any, operation: str) -> str:
    """The opening of the documentation: it carries words the name does not ("tagged", "queue")."""
    return plain_text(model.operation_model(operation).documentation, 160).split(". ")[0]


def verdict_for(model: Any, service: str, operation: str) -> Verdict:
    """Classify an operation, cross-checked with the model's HTTP method on REST protocols."""
    method = None
    if model.protocol in REST_PROTOCOLS:
        method = model.operation_model(operation).http.get("method")
    return classify_aws(service, operation, method)


def _shorten(sig: str, limit: int = 70) -> str:
    return sig if len(sig) <= limit else sig[: limit - 1] + "…"


def _parameters(input_shape: Any, detail: str) -> tuple[dict, dict]:
    required: dict = {}
    optional: dict = {}
    if not input_shape:
        return required, optional
    needed = set(input_shape.required_members)
    for name, member in input_shape.members.items():
        sig = signature(member)
        documented = {"type": sig, "doc": plain_text(member.documentation, 140)}
        if name in needed:
            required[name] = documented
        else:
            optional[name] = documented if detail == "full" else _shorten(sig)
    return required, optional


def describe_aws(model: Any, service: str, operation: str, detail: str = "brief") -> dict:
    """detail="brief": required parameters with their docs, optional ones by name and type only.
    detail="full": every parameter with its documentation (large for operations such as s3.PutObject)."""
    op = model.operation_model(operation)
    verdict = verdict_for(model, service, operation)
    required, optional = _parameters(op.input_shape, detail)
    outputs = list(op.output_shape.members) if op.output_shape else []
    out = {
        "cloud": "aws", "service": service, "operation": operation,
        "kind": verdict.kind, "destructive": verdict.destructive, "sensitive": verdict.sensitive,
        "summary": summary(op.documentation),
        "required": required, "optional": optional,
        "returns": outputs[:25] + (["…"] if len(outputs) > 25 else []),
        "call_with": "call_read" if verdict.read else "call_write",
    }
    if detail != "full" and optional:
        out["more"] = "Optional parameters are listed by name and type; describe_operation with detail='full' adds their docs."
    return out
