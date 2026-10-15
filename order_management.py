"""Read-only access to the demo order and inventory data."""

import csv
from pathlib import Path


ORDERS_FILE = Path(__file__).with_name("sample_orders.csv")
REQUIRED_COLUMNS = {
    "order_id",
    "customer",
    "product",
    "sku",
    "quantity",
    "order_status",
    "expected_delivery",
    "tracking_status",
    "estimated_delivery",
    "stock",
    "alternatives",
}


def _load_orders() -> dict[str, dict[str, str]]:
    with ORDERS_FILE.open(encoding="utf-8", newline="") as orders_file:
        reader = csv.DictReader(orders_file)
        missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(
                f"{ORDERS_FILE.name} is missing required columns: "
                f"{', '.join(sorted(missing_columns))}"
            )

        orders: dict[str, dict[str, str]] = {}
        for row in reader:
            order_id = row["order_id"].strip().upper()
            if not order_id or order_id in orders:
                raise ValueError(f"Invalid or duplicate order ID in {ORDERS_FILE.name}")
            orders[order_id] = row
        return orders


def get_order(order_id: str) -> dict[str, str]:
    """Return an order by ID, raising KeyError when it does not exist."""
    normalized_id = order_id.strip().upper()
    try:
        return _load_orders()[normalized_id]
    except KeyError as exc:
        raise KeyError(f"Order {normalized_id or '(empty)'} was not found.") from exc


def get_inventory_findings(order_id: str) -> dict[str, object]:
    """Check ordered quantity against demo stock and return alternatives."""
    order = get_order(order_id)
    stock = int(order["stock"])
    quantity = int(order["quantity"])
    return {
        "order_id": order["order_id"],
        "product": order["product"],
        "available": stock >= quantity,
        "stock": stock,
        "quantity_ordered": quantity,
        "alternative": order["alternatives"] if stock < quantity else None,
    }


def get_tracking_findings(order_id: str) -> dict[str, str]:
    """Return mock shipment status and estimate for an order."""
    order = get_order(order_id)
    return {
        "order_id": order["order_id"],
        "tracking_status": order["tracking_status"],
        "expected_delivery": order["expected_delivery"],
        "estimated_delivery": order["estimated_delivery"],
    }


def mandatory_escalation_reason(
    customer_query: str, tracking_status: str
) -> str | None:
    """Return a reason when policy requires a human to handle the case."""
    query = customer_query.casefold()
    human_request_phrases = (
        "speak to a human",
        "speak with a human",
        "talk to a human",
        "speak to a person",
        "talk to a person",
        "real person",
        "human representative",
        "human support",
    )
    if any(phrase in query for phrase in human_request_phrases):
        return "The customer explicitly asked to speak with a human representative."

    sensitive_issue_phrases = (
        "fraud",
        "chargeback",
        "legal action",
        "lawsuit",
        "injured",
        "injury",
        "unsafe",
        "safety issue",
        "payment dispute",
        "unauthorized payment",
    )
    if any(phrase in query for phrase in sensitive_issue_phrases):
        return "The complaint involves a sensitive payment, legal, or safety issue."

    if tracking_status.casefold() == "lost":
        return "The shipment is marked lost and requires human follow-up."

    return None
