"""DynamoDB domain operations for Items (no HTTP / no API Gateway)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from botocore.exceptions import ClientError


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_price(value: Any) -> Decimal:
    """Convert a JSON price to Decimal. Raises ValueError if invalid."""
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise ValueError("Field 'price' must be a valid number") from exc


def build_new_item(
    name: str,
    description: str = "",
    price: Decimal | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    item: dict[str, Any] = {
        "id": str(uuid4()),
        "name": name.strip(),
        "description": description,
        "createdAt": now,
        "updatedAt": now,
    }
    if price is not None:
        item["price"] = price
    return item


def put_item(table: Any, item: dict[str, Any]) -> None:
    table.put_item(Item=item)


def scan_items(table: Any) -> list[dict[str, Any]]:
    response = table.scan()
    return list(response.get("Items", []))


def get_item(table: Any, item_id: str) -> dict[str, Any] | None:
    response = table.get_item(Key={"id": item_id})
    item = response.get("Item")
    return item if item else None


def update_item(
    table: Any,
    item_id: str,
    update_data: dict[str, Any],
) -> dict[str, Any]:
    """Update allowed fields. Raises ClientError (incl. ConditionalCheckFailed)."""
    expr_parts: list[str] = []
    expr_names: dict[str, str] = {}
    expr_values: dict[str, Any] = {}

    for i, (key, value) in enumerate(update_data.items()):
        placeholder = f"#f{i}"
        value_ph = f":v{i}"
        expr_parts.append(f"{placeholder} = {value_ph}")
        expr_names[placeholder] = key
        if key == "price":
            expr_values[value_ph] = None if value is None else parse_price(value)
        else:
            expr_values[value_ph] = value

    expr_parts.append("#ua = :ua")
    expr_names["#ua"] = "updatedAt"
    expr_values[":ua"] = utc_now_iso()

    response = table.update_item(
        Key={"id": item_id},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ConditionExpression="attribute_exists(id)",
        ReturnValues="ALL_NEW",
    )
    return response["Attributes"]


def delete_item(table: Any, item_id: str) -> None:
    """Delete by id. Raises ClientError (incl. ConditionalCheckFailed)."""
    table.delete_item(
        Key={"id": item_id},
        ConditionExpression="attribute_exists(id)",
    )


def is_conditional_check_failed(exc: ClientError) -> bool:
    return exc.response["Error"]["Code"] == "ConditionalCheckFailedException"
