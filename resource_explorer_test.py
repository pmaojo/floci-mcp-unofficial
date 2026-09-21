import pytest
from floci_backend.application.resource_explorer import ResourceExplorer
from unittest.mock import patch, MagicMock

@pytest.fixture
def resource_explorer():
    return ResourceExplorer()

@patch('floci_backend.application.service_graph.ServiceGraph')
def test_get_relations_basic(mock_service_graph_class, resource_explorer):
    # Setup mock
    mock_sg = mock_service_graph_class.return_value
    mock_sg.build.return_value = {
        "nodes": [
            {"id": "my-lambda", "label": "my-lambda", "type": "Lambda"},
            {"id": "my-sqs", "label": "my-sqs", "type": "SQS"}
        ],
        "edges": [
            {"from": "my-sqs", "to": "my-lambda", "label": "trigger"}
        ]
    }

    # Execute
    res = resource_explorer.get_relations("my-lambda", "Lambda")

    # Assert
    assert res["resourceId"] == "my-lambda"
    assert len(res["nodes"]) >= 2

    # Check that our edge was included since it points to the target resource
    edge_found = False
    for edge in res["edges"]:
        if edge["from"] == "my-sqs" and edge["to"] == "my-lambda":
            edge_found = True
            break
    assert edge_found

@patch('floci_backend.application.resource_explorer.make_client')
@patch('floci_backend.application.service_graph.ServiceGraph')
def test_enhance_lambda_relations(mock_service_graph_class, mock_make_client, resource_explorer):
    mock_sg = mock_service_graph_class.return_value
    mock_sg.build.return_value = {"nodes": [], "edges": []}

    # Mock Lambda get_function
    mock_lambda = MagicMock()
    mock_lambda.get_function.return_value = {
        "Configuration": {
            "Environment": {
                "Variables": {
                    "TABLE_NAME": "my-dynamo-table",
                    "QUEUE_URL": "http://localhost:4566/my-sqs-queue"
                }
            }
        }
    }
    mock_make_client.return_value = mock_lambda

    res = resource_explorer.get_relations("my-function", "Lambda")

    # Check nodes
    node_ids = [n["id"] for n in res["nodes"]]
    assert "dynamodb:my-dynamo-table" in node_ids
    assert "sqs:my-sqs-queue" in node_ids

    # Check edges
    edge_labels = [e["label"] for e in res["edges"]]
    assert "env-ref" in edge_labels
