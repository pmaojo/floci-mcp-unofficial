import json
from typing import Any, Dict, List

from floci_backend.infrastructure.boto_factory import make_client

class ResourceExplorer:
    def __init__(self):
        pass

    def get_relations(self, resource_id: str, resource_type: str) -> Dict[str, Any]:
        """
        Builds a localized graph centered around a specific resource.
        Finds upstream dependencies (who triggers it) and downstream relations (what it triggers or needs).
        """
        nodes = {}
        edges = []

        def _node(n_id: str, label: str, t_name: str):
            if n_id not in nodes:
                nodes[n_id] = {"id": n_id, "label": label, "type": t_name}
            return n_id

        def _edge(src: str, dst: str, label: str):
            if src and dst:
                edges.append({"from": src, "to": dst, "label": label})

        # Add the central node
        _node(resource_id, resource_id.split(":")[-1] if ":" in resource_id else resource_id, resource_type)

        # Basic discovery: scan the global service graph and filter for our resource.
        # This is a robust approach using existing logic but isolating the specific subgraph.
        from floci_backend.application.service_graph import ServiceGraph
        sg = ServiceGraph()
        full_graph = sg.build()

        # Enhance with deeper Lambda env/role parsing if lambda is involved
        if resource_type.lower() == "lambda":
            self._enhance_lambda_relations(resource_id, _node, _edge)
        elif resource_type.lower() == "sqs":
            self._enhance_sqs_relations(resource_id, _node, _edge)
        elif resource_type.lower() == "sns":
            self._enhance_sns_relations(resource_id, _node, _edge)
        elif resource_type.lower() == "s3":
            self._enhance_s3_relations(resource_id, _node, _edge)
        elif resource_type.lower() == "dynamodb":
            self._enhance_dynamodb_relations(resource_id, _node, _edge)

        # Include any global edges that involve our resource
        for edge in full_graph.get("edges", []):
            if edge["from"] == resource_id or edge["to"] == resource_id:
                # Add nodes if they aren't already there
                for n in full_graph.get("nodes", []):
                    if n["id"] == edge["from"] or n["id"] == edge["to"]:
                        _node(n["id"], n["label"], n["type"])
                _edge(edge["from"], edge["to"], edge["label"])

        return {"resourceId": resource_id, "nodes": list(nodes.values()), "edges": edges}

    def _enhance_lambda_relations(self, resource_id: str, _node, _edge):
        try:
            lam = make_client("lambda")
            fn_name = resource_id.split(":")[-1]
            fn = lam.get_function(FunctionName=fn_name)

            # Check environment variables for clues
            env = fn.get("Configuration", {}).get("Environment", {}).get("Variables", {})
            for k, v in env.items():
                if isinstance(v, str):
                    if "dynamodb" in v.lower() or "TABLE" in k:
                        # Guessing it's a dynamo table
                        tbl = v.split("/")[-1] if "/" in v else v
                        # Just a loose association
                        _node(f"dynamodb:{tbl}", tbl, "DynamoDB")
                        _edge(resource_id, f"dynamodb:{tbl}", "env-ref")
                    elif "sqs" in v.lower() or "QUEUE" in k:
                        q = v.split("/")[-1] if "/" in v else v
                        _node(f"sqs:{q}", q, "SQS")
                        _edge(resource_id, f"sqs:{q}", "env-ref")
                    elif "s3" in v.lower() or "BUCKET" in k:
                        b = v.split("/")[-1] if "/" in v else v
                        _node(f"s3:{b}", b, "S3")
                        _edge(resource_id, f"s3:{b}", "env-ref")
        except Exception:
            pass

    def _enhance_sqs_relations(self, resource_id: str, _node, _edge):
        # Additional SQS checks could go here (e.g. KMS key)
        try:
            sqs = make_client("sqs")
            q_name = resource_id.split(":")[-1]
            url = None
            for u in sqs.list_queues().get("QueueUrls", []):
                if u.endswith(f"/{q_name}"):
                    url = u
                    break
            if url:
                attrs = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["All"]).get("Attributes", {})
                if "KmsMasterKeyId" in attrs:
                    kms_id = attrs["KmsMasterKeyId"]
                    _node(f"kms:{kms_id}", kms_id, "KMS")
                    _edge(resource_id, f"kms:{kms_id}", "encrypts")
        except Exception:
            pass

    def _enhance_sns_relations(self, resource_id: str, _node, _edge):
        try:
            sns = make_client("sns")
            attrs = sns.get_topic_attributes(TopicArn=resource_id).get("Attributes", {})
            if "KmsMasterKeyId" in attrs:
                kms_id = attrs["KmsMasterKeyId"]
                _node(f"kms:{kms_id}", kms_id, "KMS")
                _edge(resource_id, f"kms:{kms_id}", "encrypts")
        except Exception:
            pass

    def _enhance_s3_relations(self, resource_id: str, _node, _edge):
        # Not much to add that isn't in ServiceGraph, maybe KMS
        pass

    def _enhance_dynamodb_relations(self, resource_id: str, _node, _edge):
        try:
            ddb = make_client("dynamodb")
            tbl_name = resource_id.split(":")[-1]
            desc = ddb.describe_table(TableName=tbl_name).get("Table", {})
            if "SSEDescription" in desc and desc["SSEDescription"].get("Status") == "ENABLED":
                kms_id = desc["SSEDescription"].get("KMSMasterKeyArn", "AWS_OWNED_KMS_KEY")
                _node(kms_id, kms_id.split("/")[-1], "KMS")
                _edge(resource_id, kms_id, "encrypts")
        except Exception:
            pass
