"""The backend services over fake ports: no boto3, no aws CLI, no Floci.

Run with pytest or `uv run python tests/test_backend.py`.
"""
import asyncio
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from floci_backend.application.aws_resource_service import AwsResourceService  # noqa: E402
from floci_backend.application.dlq_service import DlqService  # noqa: E402
from floci_backend.application.ports import CommandError  # noqa: E402
from floci_backend.application.tags_service import TagsService  # noqa: E402


class FakeQueues:
    """In-memory SQS: {url: {"arn", "attributes", "messages"}}."""

    def __init__(self, queues):
        self.queues = queues
        self.calls = []

    def list_queue_urls(self):
        return list(self.queues)

    def queue_attributes(self, queue_url, names):
        q = self.queues[queue_url]
        attrs = {"QueueArn": q["arn"], **q.get("attributes", {}),
                 "ApproximateNumberOfMessages": str(len(q["messages"]))}
        return {k: v for k, v in attrs.items() if k in names}

    def queue_url(self, queue_name):
        for url in self.queues:
            if url.endswith("/" + queue_name):
                return url
        raise KeyError(queue_name)

    def receive(self, queue_url, *, max_messages, visibility_timeout, wait_seconds, all_attributes=False):
        self.calls.append(("receive", queue_url, max_messages, visibility_timeout, all_attributes))
        return list(self.queues[queue_url]["messages"][:max_messages])

    def send(self, queue_url, body, message_attributes):
        self.queues[queue_url]["messages"].append({"Body": body, "MessageAttributes": message_attributes})

    def delete(self, queue_url, receipt_handle):
        q = self.queues[queue_url]
        q["messages"] = [m for m in q["messages"] if m.get("ReceiptHandle") != receipt_handle]


def _queues():
    return FakeQueues({
        "http://q/000/orders": {
            "arn": "arn:aws:sqs:r:0:orders",
            "attributes": {"RedrivePolicy": json.dumps({"deadLetterTargetArn": "arn:aws:sqs:r:0:orders-dlq"})},
            "messages": [],
        },
        "http://q/000/orders-dlq": {
            "arn": "arn:aws:sqs:r:0:orders-dlq",
            "messages": [{"Body": "boom", "ReceiptHandle": "h1", "Attributes": {"ApproximateReceiveCount": "3"}}],
        },
    })


def test_dlq_lists_queues_used_as_dead_letter_targets():
    result = DlqService(_queues()).list_dead_letter_queues()
    assert result["count"] == 1
    dlq = result["deadLetterQueues"][0]
    assert dlq["name"] == "orders-dlq" and dlq["messageCount"] == 1
    assert dlq["sources"] == [{"url": "http://q/000/orders", "name": "orders"}]


def test_dlq_inspect_reads_without_hiding_messages():
    queues = _queues()
    result = DlqService(queues).inspect_messages("http://q/000/orders-dlq", 50)
    assert result["count"] == 1
    assert result["messages"][0]["failureReason"]["approximateReceiveCount"] == "3"
    assert queues.calls == [("receive", "http://q/000/orders-dlq", 10, 0, True)]


def test_dlq_redrive_moves_then_deletes():
    queues = _queues()
    result = DlqService(queues).redrive("http://q/000/orders-dlq", "http://q/000/orders", 5)
    assert result == {"redriven": 1, "target": "http://q/000/orders", "errors": []}
    assert [m["Body"] for m in queues.queues["http://q/000/orders"]["messages"]] == ["boom"]
    assert queues.queues["http://q/000/orders-dlq"]["messages"] == []


def test_dlq_unknown_arn_has_no_url_and_zero_count():
    queues = FakeQueues({"http://q/000/a": {
        "arn": "arn:aws:sqs:r:0:a",
        "attributes": {"RedrivePolicy": json.dumps({"deadLetterTargetArn": "arn:aws:sqs:r:0:gone"})},
        "messages": [],
    }})
    dlq = DlqService(queues).list_dead_letter_queues()["deadLetterQueues"][0]
    assert dlq["dlqUrl"] is None and dlq["messageCount"] == 0


class FakeTagging:
    def __init__(self, failed=None, error=None):
        self.failed, self.error, self.calls = failed or {}, error, []

    def _go(self, *call):
        self.calls.append(call)
        if self.error:
            raise self.error

    def resources(self, tag_filters=None, resource_types=None):
        self._go("resources", tag_filters, resource_types)
        return [{"ResourceARN": "arn:a"}, {"ResourceARN": "arn:b"}]

    def tag_keys(self):
        self._go("tag_keys")
        return ["b", "a"]

    def tag_values(self, key):
        self._go("tag_values", key)
        return ["y", "x"]

    def tag(self, resource_arns, tags):
        self._go("tag", resource_arns, tags)
        return self.failed

    def untag(self, resource_arns, tag_keys):
        self._go("untag", resource_arns, tag_keys)
        return self.failed


def test_tags_reads_are_sorted_and_counted():
    service = TagsService(FakeTagging())
    assert asyncio.run(service.get_tag_keys()) == {"tagKeys": ["a", "b"]}
    assert asyncio.run(service.get_tag_values("k")) == {"key": "k", "values": ["x", "y"]}
    assert asyncio.run(service.get_resources())["count"] == 2


def test_tags_partial_failure_is_reported_per_arn():
    service = TagsService(FakeTagging(failed={"arn:b": "denied"}))
    result = asyncio.run(service.tag_resources(["arn:a", "arn:b"], {"env": "dev"}))
    assert result == {"tagged": ["arn:a"], "failed": {"arn:b": "denied"}, "success": False}


def test_tags_sdk_errors_become_warnings_and_empty_input_is_rejected():
    service = TagsService(FakeTagging(error=RuntimeError("down")))
    assert asyncio.run(service.get_resources()) == {"count": 0, "resources": [], "warning": "down"}
    assert asyncio.run(service.untag_resources(["arn:a"], ["k"]))["failed"] == {"arn:a": "down"}
    try:
        asyncio.run(service.tag_resources([], {"k": "v"}))
    except ValueError:
        pass
    else:
        raise AssertionError("empty resource_arns must be rejected")


class FakeCli:
    def __init__(self, outputs):
        self.outputs, self.commands = outputs, []

    async def run_json(self, args):
        self.commands.append(args)
        out = self.outputs[args[0]]
        if isinstance(out, Exception):
            raise out
        return out


class NoCompatibility:
    def should_bypass_native(self, key):
        return False

    def can_handle(self, key):
        return False

    def can_handle_resource(self, key, resource_id):
        return False


def _single_resource_service():
    from floci_backend.application.aws_resource_catalog import AWS_RESOURCE_CATALOG
    return next((k, v) for k, v in AWS_RESOURCE_CATALOG.items() if len(v.get("resources", [])) == 1)


def test_resources_reads_through_the_cli_port():
    key, service = _single_resource_service()
    resource = service["resources"][0]
    cli = FakeCli({resource["command"][0]: {}})
    overview = asyncio.run(AwsResourceService(cli, NoCompatibility()).get_overview(key))
    assert overview["serviceKey"] == key and overview["resources"][0]["id"] == resource["id"]
    assert overview["resources"][0]["status"] == "ok"
    assert cli.commands == [resource["command"]]


def test_resources_cli_failures_are_classified_from_the_port_error():
    key, service = _single_resource_service()
    cmd = service["resources"][0]["command"][0]
    unsupported = CommandError("x", "", "An error occurred (UnsupportedOperation)", 255)
    result = asyncio.run(AwsResourceService(FakeCli({cmd: unsupported}), NoCompatibility()).get_overview(key))
    assert result["resources"][0]["status"] == "unsupported"
    broken = CommandError("x", "", "boom", 1)
    result = asyncio.run(AwsResourceService(FakeCli({cmd: broken}), NoCompatibility()).get_overview(key))
    assert result["resources"][0]["status"] == "error" and result["resources"][0]["error"] == "boom"


def test_the_infrastructure_cli_error_is_a_command_error():
    from floci_backend.infrastructure.aws_cli import AwsCliError
    assert issubclass(AwsCliError, CommandError)


if __name__ == "__main__":
    failed = 0
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            fn()
            print(f"ok    {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {type(exc).__name__}: {str(exc)[:400]}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
