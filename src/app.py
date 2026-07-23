import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

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
    """POST /items – create a new item."""
    try:
        data = _parse_body(event)
    except ValueError as e:
        return _response(400, {"error": str(e)})

    name = data.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        return _response(400, {"error": "Field 'name' is required and must be a non-empty string"})

    item_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    price = None
    if "price" in data and data["price"] is not None:
        try:
            price = Decimal(str(data["price"]))
        except (ValueError, TypeError, ArithmeticError):
            return _response(400, {"error": "Field 'price' must be a valid number"})

    item = {
        "id": item_id,
        "name": name.strip(),
        "description": data.get("description", ""),
        "price": price,
        "createdAt": now,
        "updatedAt": now,
    }

    # Remove None values for cleaner DynamoDB item
    item = {k: v for k, v in item.items() if v is not None}

    try:
        table.put_item(Item=item)
    except ClientError as e:
        return _response(500, {"error": "Failed to create item", "details": e.response["Error"]["Message"]})

    return _response(201, item)


def list_items(event: dict) -> dict:
    """GET /items – list all items (scan – fine for demo / small tables)."""
    try:
        response = table.scan()
        items = response.get("Items", [])
        # Optional simple pagination could be added later with ExclusiveStartKey
        return _response(200, {"items": items, "count": len(items)})
    except ClientError as e:
        return _response(500, {"error": "Failed to list items", "details": e.response["Error"]["Message"]})


def get_item(event: dict) -> dict:
    """GET /items/{id} – retrieve a single item."""
    item_id = _get_path_param(event, "id")
    if not item_id:
        return _response(400, {"error": "Missing path parameter 'id'"})

    try:
        response = table.get_item(Key={"id": item_id})
        item = response.get("Item")
        if not item:
            return _response(404, {"error": f"Item with id '{item_id}' not found"})
        return _response(200, item)
    except ClientError as e:
        return _response(500, {"error": "Failed to get item", "details": e.response["Error"]["Message"]})


def update_item(event: dict) -> dict:
    """PUT /items/{id} – update an existing item."""
    item_id = _get_path_param(event, "id")
    if not item_id:
        return _response(400, {"error": "Missing path parameter 'id'"})

    try:
        data = _parse_body(event)
    except ValueError as e:
        return _response(400, {"error": str(e)})

    if not data:
        return _response(400, {"error": "Request body cannot be empty"})

    # Only allow updating these fields
    allowed = {"name", "description", "price"}
    update_data = {k: v for k, v in data.items() if k in allowed}

    if not update_data:
        return _response(400, {"error": "No valid fields to update. Allowed: name, description, price"})

    # Build UpdateExpression dynamically
    expr_parts = []
    expr_names = {}
    expr_values = {}

    for i, (key, value) in enumerate(update_data.items()):
        placeholder = f"#f{i}"
        value_ph = f":v{i}"
        expr_parts.append(f"{placeholder} = {value_ph}")
        expr_names[placeholder] = key
        if key == "price":
            if value is None:
                expr_values[value_ph] = None
            else:
                try:
                    expr_values[value_ph] = Decimal(str(value))
                except (ValueError, TypeError, ArithmeticError):
                    return _response(400, {"error": "Field 'price' must be a valid number"})
        else:
            expr_values[value_ph] = value

    # Always update updatedAt
    expr_parts.append("#ua = :ua")
    expr_names["#ua"] = "updatedAt"
    expr_values[":ua"] = datetime.now(timezone.utc).isoformat()

    update_expression = "SET " + ", ".join(expr_parts)

    try:
        response = table.update_item(
            Key={"id": item_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ConditionExpression="attribute_exists(id)",
            ReturnValues="ALL_NEW",
        )
        return _response(200, response["Attributes"])
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _response(404, {"error": f"Item with id '{item_id}' not found"})
        return _response(500, {"error": "Failed to update item", "details": e.response["Error"]["Message"]})


def delete_item(event: dict) -> dict:
    """DELETE /items/{id} – delete an item."""
    item_id = _get_path_param(event, "id")
    if not item_id:
        return _response(400, {"error": "Missing path parameter 'id'"})

    try:
        # Use ConditionExpression to distinguish not-found from success
        table.delete_item(
            Key={"id": item_id},
            ConditionExpression="attribute_exists(id)",
        )
        return _response(204, None)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _response(404, {"error": f"Item with id '{item_id}' not found"})
        return _response(500, {"error": "Failed to delete item", "details": e.response["Error"]["Message"]})


def _get_method_and_path(event: dict) -> tuple[str, str]:
    """
    Extract HTTP method and path supporting both
    API Gateway REST (v1) and HTTP API (v2 / payload format 2.0).
    """
    # Payload format 2.0 (HTTP API)
    if "requestContext" in event and "http" in event["requestContext"]:
        method = event["requestContext"]["http"].get("method", "").upper()
        path = event.get("rawPath") or event["requestContext"]["http"].get("path", "")
    else:
        # Payload format 1.0 (REST API)
        method = event.get("httpMethod", "").upper()
        path = event.get("path") or event.get("resource", "")

    # Strip stage prefix if present (e.g. /prod/items -> /items)
    # Common when using REST API or custom domain mapping
    if path.startswith("/prod/"):
        path = path[5:]
    elif path.startswith("/prod"):
        path = path[4:] or "/"

    # Normalize trailing slash
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    return method, path


def lambda_handler(event: dict, context) -> dict:
    """
    Main entry point for API Gateway (proxy integration).
    Supports both REST API (v1) and HTTP API (v2).
    Routes based on HTTP method + path.
    """
    method, path = _get_method_and_path(event)

    # Handle CORS preflight
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
        # Catch-all for unexpected errors (log in real deployments)
        return _response(500, {"error": "Internal server error", "details": str(e)})
