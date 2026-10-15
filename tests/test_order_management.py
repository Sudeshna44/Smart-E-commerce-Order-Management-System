import pytest

from order_management import (
    get_inventory_findings,
    get_order,
    get_tracking_findings,
    mandatory_escalation_reason,
)


def test_delayed_order_has_stock_and_revised_estimate():
    assert get_inventory_findings("ORD1025")["available"] is True
    tracking = get_tracking_findings("ORD1025")
    assert tracking["tracking_status"] == "delayed"
    assert tracking["estimated_delivery"] == "2026-10-17"


def test_delivered_order_tracking():
    assert get_tracking_findings("ORD1001")["tracking_status"] == "delivered"


def test_out_of_stock_order_suggests_alternative():
    findings = get_inventory_findings("ORD1002")
    assert findings["available"] is False
    assert findings["alternative"] == "Bluetooth Mini Speaker"


def test_unknown_order_is_reported():
    with pytest.raises(KeyError, match="was not found"):
        get_order("ORD9999")


@pytest.mark.parametrize(
    ("query", "tracking_status", "expected"),
    [
        ("I want to speak to a human representative.", "delayed", True),
        ("Please reverse this unauthorized payment.", "delivered", True),
        ("My parcel hasn't arrived yet.", "delayed", False),
        ("Where is my order?", "delivered", False),
    ],
)
def test_human_escalation_policy(query, tracking_status, expected):
    assert bool(mandatory_escalation_reason(query, tracking_status)) is expected


def test_lost_shipment_requires_human_follow_up():
    assert mandatory_escalation_reason("Where is my parcel?", "lost")
