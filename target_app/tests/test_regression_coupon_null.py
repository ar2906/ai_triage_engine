"""
Regression test for coupon null-safety bug (commit 6dce9e7).
Tests that orders with null coupons, missing coupon fields, and valid coupons
are handled correctly without raising TypeError.
"""
import pytest
from fastapi.testclient import TestClient
from target_app.main import app

client = TestClient(app)


def test_order_with_null_coupon():
    """
    Test that reproduces the original bug: order with coupon=null.
    This should NOT raise TypeError: 'NoneType' object is not subscriptable.
    """
    payload = {
        "order_id": "ORD-999",
        "amount": 50.0,
        "coupon": None
    }
    
    response = client.post("/orders", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "ORD-999"
    assert data["amount"] == 50.0
    assert data["discount"] == 0.0
    assert data["final_total"] == 50.0
    assert data["status"] == "created"


def test_order_without_coupon_field():
    """
    Test order submission without coupon field at all (defaults to None).
    """
    payload = {
        "order_id": "ORD-1000",
        "amount": 100.0
    }
    
    response = client.post("/orders", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "ORD-1000"
    assert data["amount"] == 100.0
    assert data["discount"] == 0.0
    assert data["final_total"] == 100.0
    assert data["status"] == "created"


def test_order_with_empty_coupon_dict():
    """
    Test order with coupon as empty dict (missing 'percent' key).
    Should not raise KeyError.
    """
    payload = {
        "order_id": "ORD-1001",
        "amount": 75.0,
        "coupon": {}
    }
    
    response = client.post("/orders", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "ORD-1001"
    assert data["amount"] == 75.0
    assert data["discount"] == 0.0
    assert data["final_total"] == 75.0
    assert data["status"] == "created"


def test_order_with_coupon_missing_percent():
    """
    Test order with coupon dict that has other keys but not 'percent'.
    """
    payload = {
        "order_id": "ORD-1002",
        "amount": 60.0,
        "coupon": {"code": "SAVE10"}
    }
    
    response = client.post("/orders", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "ORD-1002"
    assert data["amount"] == 60.0
    assert data["discount"] == 0.0
    assert data["final_total"] == 60.0
    assert data["status"] == "created"


def test_order_with_valid_coupon():
    """
    Test order with valid coupon containing 'percent' key.
    This should apply the discount correctly.
    """
    payload = {
        "order_id": "ORD-1003",
        "amount": 100.0,
        "coupon": {"percent": 20}
    }
    
    response = client.post("/orders", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "ORD-1003"
    assert data["amount"] == 100.0
    assert data["discount"] == 20.0
    assert data["final_total"] == 80.0
    assert data["status"] == "created"


def test_order_with_10_percent_coupon():
    """
    Test order with 10% discount coupon.
    """
    payload = {
        "order_id": "ORD-1004",
        "amount": 50.0,
        "coupon": {"percent": 10}
    }
    
    response = client.post("/orders", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "ORD-1004"
    assert data["amount"] == 50.0
    assert data["discount"] == 5.0
    assert data["final_total"] == 45.0
    assert data["status"] == "created"


def test_order_with_zero_percent_coupon():
    """
    Test edge case: coupon with 0% discount.
    """
    payload = {
        "order_id": "ORD-1005",
        "amount": 80.0,
        "coupon": {"percent": 0}
    }
    
    response = client.post("/orders", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "ORD-1005"
    assert data["amount"] == 80.0
    assert data["discount"] == 0.0
    assert data["final_total"] == 80.0
    assert data["status"] == "created"
