"""The backend services over fake ports: no boto3, no aws CLI, no Floci.

Run with pytest or `uv run python tests/test_backend.py`.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from floci_backend.application.dlq_service import DlqService  # noqa: E402


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
