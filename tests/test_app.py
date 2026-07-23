"""
Unit tests for the CRUD Lambda handler.

Uses moto to mock DynamoDB so tests run offline and do not touch real AWS.
Run with:

    pip install -r requirements.txt
    PYTHONPATH=. pytest tests/ -v
"""

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

# Ensure project root is on PYTHONPATH so "from src.app import ..." works
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["TABLE_NAME"] = "Items"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"


@pytest.fixture
def dynamodb_table():
    """Create a mocked DynamoDB table and re-bind the module-level table object."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        tbl = dynamodb.create_table(
            TableName="Items",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Re-import / re-bind so the global `table` inside src.app points to the mocked table
        import src.app as app_module
        app_module.table = tbl
        app_module.dynamodb = dynamodb

        yield tbl


def _make_event(
    method: str,
    path: str,
    body: dict | None = None,
    path_params: dict | None = None,
    is_v2: bool = True,
) -> dict:
    """Helper to build a minimal API Gateway event (v2 by default)."""
    event = {
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
        "pathParameters": path_params or {},
    }

    if is_v2:
        event["version"] = "2.0"
        event["rawPath"] = path
        event["requestContext"] = {
            "http": {
                "method": method,
                "path": path,
            }
        }
    else:
        event["httpMethod"] = method
        event["path"] = path
        event["resource"] = path

    return event


# ---------- CREATE ----------

def test_create_item_success(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("POST", "/items", {"name": "Notebook", "description": "Dell XPS", "price": 4599.90})
    response = lambda_handler(event, None)

    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["name"] == "Notebook"
    assert body["description"] == "Dell XPS"
    assert body["price"] == 4599.90
    assert "id" in body
    assert "createdAt" in body
    assert "updatedAt" in body

    # Verify it was actually written
    item = dynamodb_table.get_item(Key={"id": body["id"]})["Item"]
    assert item["name"] == "Notebook"


def test_create_item_missing_name(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("POST", "/items", {"description": "no name"})
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "name" in body["error"].lower()


def test_create_item_invalid_price(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("POST", "/items", {"name": "Bad Price", "price": "not-a-number"})
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "price" in body["error"].lower()


def test_create_item_empty_body(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("POST", "/items", None)
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400


def test_create_item_invalid_json(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("POST", "/items")
    event["body"] = "{invalid"
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400


# ---------- LIST ----------

def test_list_items_empty(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("GET", "/items")
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["items"] == []
    assert body["count"] == 0


def test_list_items_with_data(dynamodb_table):
    from src.app import lambda_handler

    # Seed two items
    dynamodb_table.put_item(Item={"id": "1", "name": "A", "createdAt": "2026-01-01T00:00:00+00:00"})
    dynamodb_table.put_item(Item={"id": "2", "name": "B", "createdAt": "2026-01-02T00:00:00+00:00"})

    event = _make_event("GET", "/items")
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["count"] == 2
    names = {i["name"] for i in body["items"]}
    assert names == {"A", "B"}


# ---------- GET ----------

def test_get_item_success(dynamodb_table):
    from src.app import lambda_handler

    dynamodb_table.put_item(
        Item={
            "id": "abc-123",
            "name": "Keyboard",
            "price": Decimal("199.90"),
            "createdAt": "2026-01-01T00:00:00+00:00",
        }
    )
    event = _make_event("GET", "/items/abc-123", path_params={"id": "abc-123"})
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "abc-123"
    assert body["name"] == "Keyboard"
    assert body["price"] == 199.90


def test_get_item_not_found(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("GET", "/items/does-not-exist", path_params={"id": "does-not-exist"})
    response = lambda_handler(event, None)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "not found" in body["error"].lower()


def test_get_item_missing_id(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("GET", "/items/", path_params={})
    response = lambda_handler(event, None)
    assert response["statusCode"] in (400, 404)


# ---------- UPDATE ----------

def test_update_item_success(dynamodb_table):
    from src.app import lambda_handler

    dynamodb_table.put_item(
        Item={
            "id": "upd-1",
            "name": "Old Name",
            "description": "Old desc",
            "createdAt": "2026-01-01T00:00:00+00:00",
            "updatedAt": "2026-01-01T00:00:00+00:00",
        }
    )
    event = _make_event(
        "PUT",
        "/items/upd-1",
        body={"name": "New Name", "price": 99.50},
        path_params={"id": "upd-1"},
    )
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["name"] == "New Name"
    assert body["price"] == 99.50
    assert body["description"] == "Old desc"  # unchanged
    assert body["updatedAt"] > body["createdAt"]


def test_update_item_not_found(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event(
        "PUT",
        "/items/missing",
        body={"name": "Whatever"},
        path_params={"id": "missing"},
    )
    response = lambda_handler(event, None)
    assert response["statusCode"] == 404


def test_update_item_no_valid_fields(dynamodb_table):
    from src.app import lambda_handler

    dynamodb_table.put_item(Item={"id": "x", "name": "Y"})
    event = _make_event(
        "PUT",
        "/items/x",
        body={"unknown_field": 123},
        path_params={"id": "x"},
    )
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400


# ---------- DELETE ----------

def test_delete_item_success(dynamodb_table):
    from src.app import lambda_handler

    dynamodb_table.put_item(Item={"id": "del-1", "name": "To delete"})
    event = _make_event("DELETE", "/items/del-1", path_params={"id": "del-1"})
    response = lambda_handler(event, None)
    assert response["statusCode"] == 204
    assert response["body"] == ""

    # Confirm gone
    result = dynamodb_table.get_item(Key={"id": "del-1"})
    assert "Item" not in result


def test_delete_item_not_found(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("DELETE", "/items/ghost", path_params={"id": "ghost"})
    response = lambda_handler(event, None)
    assert response["statusCode"] == 404


# ---------- ROUTING / EDGE ----------

def test_unknown_route(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("GET", "/unknown")
    response = lambda_handler(event, None)
    assert response["statusCode"] == 404


def test_options_cors(dynamodb_table):
    from src.app import lambda_handler

    event = _make_event("OPTIONS", "/items")
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    assert "Access-Control-Allow-Origin" in response["headers"]


def test_v1_payload_format(dynamodb_table):
    """Ensure REST API (payload 1.0) still works."""
    from src.app import lambda_handler

    event = _make_event("POST", "/items", {"name": "V1 Item"}, is_v2=False)
    response = lambda_handler(event, None)
    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["name"] == "V1 Item"
