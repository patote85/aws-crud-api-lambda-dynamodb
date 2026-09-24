"""
HTTP contract tests via lambda_handler + API Gateway events (payload 2.0).

Prove-it-works suite for make verify: real status codes and body shapes
for CRUD routes (POST/GET/PUT/DELETE /items).

    pip install -r requirements.txt
    PYTHONPATH=. pytest tests/test_http_contract.py -v
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import boto3
import pytest
from moto import mock_aws

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["TABLE_NAME"] = "Items"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"


@pytest.fixture
def dynamodb_table():
    """Mock DynamoDB and re-bind src.app module-level table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        tbl = dynamodb.create_table(
            TableName="Items",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        import src.app as app_module

        app_module.table = tbl
        app_module.dynamodb = dynamodb
        yield tbl


def make_http_event(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    path_parameters: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Minimal API Gateway HTTP API (payload 2.0) event."""
    event: dict[str, Any] = {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "domainName": "localhost",
            "domainPrefix": "localhost",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            },
            "requestId": "test-request-id",
            "routeKey": f"{method} {path}",
            "stage": "$default",
            "time": "01/Jan/2026:00:00:00 +0000",
            "timeEpoch": 1767225600000,
        },
        "isBase64Encoded": False,
        "pathParameters": path_parameters or {},
    }
    if body is not None:
        event["body"] = json.dumps(body)
    else:
        event["body"] = None
    return event


def _invoke(
    method: str,
    path: str,
    body: dict | None = None,
    path_parameters: dict[str, str] | None = None,
) -> dict:
    from src.app import lambda_handler

    return lambda_handler(
        make_http_event(method, path, body=body, path_parameters=path_parameters),
        None,
    )


def _body(resp: dict) -> dict:
    return json.loads(resp["body"])


def test_list_items_empty_returns_200_count_zero(dynamodb_table):
    resp = _invoke("GET", "/items")
    assert resp["statusCode"] == 200
    assert _body(resp) == {"items": [], "count": 0}


def test_create_item_returns_201_with_id_and_name(dynamodb_table):
    resp = _invoke(
        "POST",
        "/items",
        body={"name": "Contract Item", "description": "via http contract", "price": 10.5},
    )
    assert resp["statusCode"] == 201
    body = _body(resp)
    assert body["name"] == "Contract Item"
    assert body["description"] == "via http contract"
    assert body["price"] == 10.5
    assert isinstance(body["id"], str) and body["id"]
    assert "createdAt" in body and "updatedAt" in body


def test_create_item_missing_name_returns_400(dynamodb_table):
    resp = _invoke("POST", "/items", body={"description": "no name"})
    assert resp["statusCode"] == 400
    assert "name" in _body(resp)["error"].lower()


def test_happy_path_create_get_update_delete(dynamodb_table):
    # 1) create
    created = _invoke(
        "POST",
        "/items",
        body={"name": "Widget", "price": 42},
    )
    assert created["statusCode"] == 201
    item_id = _body(created)["id"]

    # 2) get
    got = _invoke("GET", f"/items/{item_id}", path_parameters={"id": item_id})
    assert got["statusCode"] == 200
    assert _body(got)["id"] == item_id
    assert _body(got)["name"] == "Widget"

    # 3) list includes it
    listed = _invoke("GET", "/items")
    assert listed["statusCode"] == 200
    assert _body(listed)["count"] == 1
    assert _body(listed)["items"][0]["id"] == item_id

    # 4) update
    updated = _invoke(
        "PUT",
        f"/items/{item_id}",
        body={"name": "Widget Pro", "price": 99.9},
        path_parameters={"id": item_id},
    )
    assert updated["statusCode"] == 200
    assert _body(updated)["name"] == "Widget Pro"
    assert _body(updated)["price"] == 99.9

    # 5) delete
    deleted = _invoke("DELETE", f"/items/{item_id}", path_parameters={"id": item_id})
    assert deleted["statusCode"] == 204
    assert deleted["body"] == ""

    # 6) get after delete → 404
    missing = _invoke("GET", f"/items/{item_id}", path_parameters={"id": item_id})
    assert missing["statusCode"] == 404
    assert "not found" in _body(missing)["error"].lower()


def test_get_item_not_found_returns_404(dynamodb_table):
    resp = _invoke("GET", "/items/does-not-exist", path_parameters={"id": "does-not-exist"})
    assert resp["statusCode"] == 404
    assert "not found" in _body(resp)["error"].lower()


def test_unknown_route_returns_404(dynamodb_table):
    resp = _invoke("GET", "/unknown")
    assert resp["statusCode"] == 404
    assert "route not found" in _body(resp)["error"].lower()


def test_options_preflight_returns_200_with_cors_headers(dynamodb_table):
    resp = _invoke("OPTIONS", "/items")
    assert resp["statusCode"] == 200
    assert "Access-Control-Allow-Origin" in resp["headers"]
    assert "Access-Control-Allow-Methods" in resp["headers"]
