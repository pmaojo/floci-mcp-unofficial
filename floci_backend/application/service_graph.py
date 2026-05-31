"""X-Ray-style service graph (Area 3 — Observability).

Builds a graph of nodes and edges that reflects the REAL relationships between
emulator resources (not just an inventory): SNS→SQS subscriptions, Lambda event
source mappings, EventBridge rule→targets, SQS→DLQ redrive and S3→Lambda
notifications. Used to render the full trace of an asynchronous event in the
cockpit.
"""
import json
from typing import Any, Dict, List

from floci_backend.infrastructure.boto_factory import make_client


class ServiceGraph:
    def __init__(self):
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []

    def _node(self, node_id: str, label: str, type_name: str) -> str:
        if node_id not in self._nodes:
            self._nodes[node_id] = {"id": node_id, "label": label, "type": type_name}
        return node_id

    def _edge(self, src: str, dst: str, label: str) -> None:
        if src and dst:
            self._edges.append({"from": src, "to": dst, "label": label})

    def build(self) -> Dict[str, Any]:
        self._nodes = {}
        self._edges = []

        # --- Base inventory + relationships ---
        self._scan_sqs()
        self._scan_sns()
        self._scan_lambda()
        self._scan_eventbridge()
        self._scan_s3()

        return {"nodes": list(self._nodes.values()), "edges": self._edges}

    def _arn_id(self, arn: str) -> str:
        return arn

    def _scan_sqs(self) -> None:
        try:
            sqs = make_client("sqs")
            for url in sqs.list_queues().get("QueueUrls", []):
                name = url.split("/")[-1]
                attrs = sqs.get_queue_attributes(
                    QueueUrl=url, AttributeNames=["QueueArn", "RedrivePolicy"]
                ).get("Attributes", {})
                arn = attrs.get("QueueArn", f"sqs:{name}")
                self._node(arn, name, "SQS")
                if redrive := attrs.get("RedrivePolicy"):
                    try:
                        dlq_arn = json.loads(redrive).get("deadLetterTargetArn")
                        if dlq_arn:
                            self._node(dlq_arn, dlq_arn.split(":")[-1], "SQS")
                            self._edge(arn, dlq_arn, "dead-letter")
                    except (json.JSONDecodeError, TypeError):
                        pass
        except Exception:
            pass

    def _scan_sns(self) -> None:
        try:
            sns = make_client("sns")
            for topic in sns.list_topics().get("Topics", []):
                arn = topic["TopicArn"]
                self._node(arn, arn.split(":")[-1], "SNS")
                subs = sns.list_subscriptions_by_topic(TopicArn=arn).get("Subscriptions", [])
                for sub in subs:
                    endpoint = sub.get("Endpoint", "")
                    proto = sub.get("Protocol")
                    if proto == "sqs":
                        self._node(endpoint, endpoint.split(":")[-1], "SQS")
                        self._edge(arn, endpoint, "subscribe")
                    elif proto == "lambda":
                        self._node(endpoint, endpoint.split(":")[-1], "Lambda")
                        self._edge(arn, endpoint, "subscribe")
        except Exception:
            pass

    def _scan_lambda(self) -> None:
        try:
            lam = make_client("lambda")
            for fn in lam.list_functions().get("Functions", []):
                fn_arn = fn["FunctionArn"]
                self._node(fn_arn, fn["FunctionName"], "Lambda")
                try:
                    mappings = lam.list_event_source_mappings(
                        FunctionName=fn["FunctionName"]
                    ).get("EventSourceMappings", [])
                    for m in mappings:
                        src = m.get("EventSourceArn")
                        if src:
                            stype = "SQS" if ":sqs:" in src else "Kinesis" if ":kinesis:" in src else "DynamoDB" if ":dynamodb:" in src else "Source"
                            self._node(src, src.split(":")[-1], stype)
                            self._edge(src, fn_arn, "trigger")
                except Exception:
                    pass
        except Exception:
            pass

    def _scan_eventbridge(self) -> None:
        try:
            events = make_client("events")
            buses = events.list_event_buses().get("EventBuses", [])
            for bus in buses:
                bus_name = bus["Name"]
                rules = events.list_rules(EventBusName=bus_name).get("Rules", [])
                for rule in rules:
                    rule_arn = rule.get("Arn", f"rule:{rule['Name']}")
                    self._node(rule_arn, rule["Name"], "EventBridge")
                    targets = events.list_targets_by_rule(
                        Rule=rule["Name"], EventBusName=bus_name
                    ).get("Targets", [])
                    for t in targets:
                        t_arn = t["Arn"]
                        ttype = "Lambda" if ":lambda:" in t_arn else "SQS" if ":sqs:" in t_arn else "SNS" if ":sns:" in t_arn else "Target"
                        self._node(t_arn, t_arn.split(":")[-1], ttype)
                        self._edge(rule_arn, t_arn, "route")
        except Exception:
            pass

    def _scan_s3(self) -> None:
        try:
            s3 = make_client("s3")
            for bucket in s3.list_buckets().get("Buckets", []):
                name = bucket["Name"]
                b_id = f"s3:{name}"
                self._node(b_id, name, "S3")
                try:
                    cfg = s3.get_bucket_notification_configuration(Bucket=name)
                    for lc in cfg.get("LambdaFunctionConfigurations", []):
                        fn_arn = lc.get("LambdaFunctionArn")
                        if fn_arn:
                            self._node(fn_arn, fn_arn.split(":")[-1], "Lambda")
                            self._edge(b_id, fn_arn, "s3:event")
                    for qc in cfg.get("QueueConfigurations", []):
                        q_arn = qc.get("QueueArn")
                        if q_arn:
                            self._node(q_arn, q_arn.split(":")[-1], "SQS")
                            self._edge(b_id, q_arn, "s3:event")
                except Exception:
                    pass
        except Exception:
            pass
