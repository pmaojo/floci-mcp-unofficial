"""Which AWS services answer on the running Floci."""
from concurrent.futures import ThreadPoolExecutor

from botocore.exceptions import EndpointConnectionError

from floci_generic import catalog
from floci_generic.classify import split_name

NOT_IMPLEMENTED = ("NotImplemented", "UnknownOperation", "UnsupportedOperation", "InvalidAction", "UnrecognizedClient")
_VERB_ORDER = {"list": 0, "describe": 1, "get": 2}


def _candidates(service: str, attempts: int) -> list[str]:
    """Argument-free, non-secret reads of a service, lists first."""
    model = catalog.aws_model(service)
    found = []
    for name in model.operation_names:
        shape = model.operation_model(name).input_shape
        verdict = catalog.aws_verdict(service, name)
        if verdict.read and not verdict.sensitive and not (shape and shape.required_members):
            found.append(name)
    found.sort(key=lambda n: (_VERB_ORDER.get(split_name(n)[0], 3), n))
    return found[:attempts]


def _answers(result: dict) -> bool:
    """An error the service itself raised still means it understood the request."""
    code = result.get("error", "")
    return not code or not any(marker in code for marker in NOT_IMPLEMENTED)


def probe_aws(services: "list[str] | None" = None, workers: int = 16, attempts: int = 6) -> dict[str, str]:
    """service -> answers | not-implemented | unreachable | no-argument-free-read | error: <type>.

    A service answers when any of a few argument-free reads works. One failing operation says
    nothing about the service: Floci may implement ListTables and not DescribeEndpoints.
    """
    from floci_generic.gateway import Gateway

    gateway = Gateway()

    def one(service: str) -> tuple[str, str]:
        names = _candidates(service, attempts)
        if not names:
            return service, "no-argument-free-read"
        outcome = "not-implemented"
        for name in names:
            try:
                result = gateway.aws_call(service, name, {})
            except EndpointConnectionError:
                return service, "unreachable"
            except Exception as exc:  # noqa: BLE001 - one odd operation must not hide the rest
                outcome = f"error: {type(exc).__name__}"
                continue
            if _answers(result):
                return service, "answers"
        return service, outcome

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(one, services or catalog.aws_services()))
