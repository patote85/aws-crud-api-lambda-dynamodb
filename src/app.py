import json
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

try:
    import domain_items as domain  # Lambda CodeUri=src/
except ImportError:  # local: PYTHONPATH=. + from src.app import ...
    from src import domain_items as domain

# DynamoDB resource (initialized once per cold start)
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("TABLE_NAME", "Items")
table = dynamodb.Table(table_name)


def _response(status_code: int, body: dict | list | None = None, headers: dict | None = None) -> dict:
    """Build a standard API Gateway proxy response with CORS."""
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    }
    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body, default=_decimal_default) if body is not None else "",
    }


def _decimal_default(obj):
    """JSON serializer for Decimal (DynamoDB numbers)."""
    if isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _parse_body(event: dict) -> dict:
    """Parse and validate JSON body from the event."""
    body = event.get("body")
    if not body:
        return {}
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode("utf-8")
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("Invalid JSON body")


def _get_path_param(event: dict, name: str) -> str | None:
    """Extract path parameter safely."""
    params = event.get("pathParameters") or {}
    return params.get(name)


def create_item(event: dict) -> dict:
    """POST /items - create a new item."""
    try:
        data = _parse_body(event)
    except ValueError as e:
        return _response(400, {"error": str(e)})

    name = data.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        return _response(400, {"error": "Field 'name' is required and must be a non-empty string"})

    price = None
    if "price" in data and data["price"] is not None:
        try:
            price = domain.parse_price(data["price"])
        except ValueError as e:
            return _response(400, {"error": str(e)})

    item = domain.build_new_item(
        name=name,
        description=data.get("description", ""),
        price=price,
    )

    try:
        domain.put_item(table, item)
    except ClientError as e:
        return _response(500, {"error": "Failed to create item", "details": e.response["Error"]["Message"]})

    return _response(201, item)


def list_items(event: dict) -> dict:
    """GET /items - list all items (scan - fine for demo / small tables)."""
    try:
        items = domain.scan_items(table)
        return _response(200, {"items": items, "count": len(items)})
    except ClientError as e:
        return _response(500, {"error": "Failed to list items", "details": e.response["Error"]["Message"]})


def get_item(event: dict) -> dict:
    """GET /items/{id} - retrieve a single item."""
    item_id = _get_path_param(event, "id")
    if not item_id:
        return _response(400, {"error": "Missing path parameter 'id'"})

    try:
        item = domain.get_item(table, item_id)
        if not item:
            return _response(404, {"error": f"Item with id '{item_id}' not found"})
        return _response(200, item)
    except ClientError as e:
        return _response(500, {"error": "Failed to get item", "details": e.response["Error"]["Message"]})


def update_item(event: dict) -> dict:
    """PUT /items/{id} - update an existing item."""
    item_id = _get_path_param(event, "id")
    if not item_id:
        return _response(400, {"error": "Missing path parameter 'id'"})

    try:
        data = _parse_body(event)
    except ValueError as e:
        return _response(400, {"error": str(e)})

    if not data:
        return _response(400, {"error": "Request body cannot be empty"})

    allowed = {"name", "description", "price"}
    update_data = {k: v for k, v in data.items() if k in allowed}

    if not update_data:
        return _response(400, {"error": "No valid fields to update. Allowed: name, description, price"})

    try:
        # Validate price early for a clean 400 (domain.parse_price inside update also raises)
        if "price" in update_data and update_data["price"] is not None:
            update_data["price"] = domain.parse_price(update_data["price"])
        attributes = domain.update_item(table, item_id, update_data)
        return _response(200, attributes)
    except ValueError as e:
        return _response(400, {"error": str(e)})
    except ClientError as e:
        if domain.is_conditional_check_failed(e):
            return _response(404, {"error": f"Item with id '{item_id}' not found"})
        return _response(500, {"error": "Failed to update item", "details": e.response["Error"]["Message"]})


def delete_item(event: dict) -> dict:
    """DELETE /items/{id} - delete an item."""
    item_id = _get_path_param(event, "id")
    if not item_id:
        return _response(400, {"error": "Missing path parameter 'id'"})

    try:
        domain.delete_item(table, item_id)
        return _response(204, None)
    except ClientError as e:
        if domain.is_conditional_check_failed(e):
            return _response(404, {"error": f"Item with id '{item_id}' not found"})
        return _response(500, {"error": "Failed to delete item", "details": e.response["Error"]["Message"]})


def _get_method_and_path(event: dict) -> tuple[str, str]:
    """
    Extract HTTP method and path supporting both
    API Gateway REST (v1) and HTTP API (v2 / payload format 2.0).
    """
    if "requestContext" in event and "http" in event["requestContext"]:
        method = event["requestContext"]["http"].get("method", "").upper()
        path = event.get("rawPath") or event["requestContext"]["http"].get("path", "")
    else:
        method = event.get("httpMethod", "").upper()
        path = event.get("path") or event.get("resource", "")

    if path.startswith("/prod/"):
        path = path[5:]
    elif path.startswith("/prod"):
        path = path[4:] or "/"

    if path != "/" and path.endswith("/") and path != "/items/":
        path = path.rstrip("/")

    return method, path


def lambda_handler(event: dict, context) -> dict:
    """
    Main entry point for API Gateway (proxy integration).
    Supports both REST API (v1) and HTTP API (v2).
    Routes based on HTTP method + path.
    """
    method, path = _get_method_and_path(event)

    if method == "OPTIONS":
        return _response(200, None)

    try:
        if method == "POST" and path == "/items":
            return create_item(event)
        if method == "GET" and path == "/items":
            return list_items(event)
        if method == "GET" and path.startswith("/items/"):
            return get_item(event)
        if method == "PUT" and path.startswith("/items/"):
            return update_item(event)
        if method == "DELETE" and path.startswith("/items/"):
            return delete_item(event)

        return _response(404, {"error": f"Route not found: {method} {path}"})
    except Exception as e:
        return _response(500, {"error": "Internal server error", "details": str(e)})
