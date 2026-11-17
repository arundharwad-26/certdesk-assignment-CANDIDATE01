"""Starter tests. Some of these fail on purpose until you finish the task.

Add your own tests (at least 5) in this file or in new test files.
"""
from datetime import date

from app.helpers import paginate, parse_date


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_parse_date_reads_year_month_day():
    assert parse_date("2026-03-25") == date(2026, 3, 25)


def test_paginate_first_page_starts_at_zero():
    assert paginate(1, 10) == (0, 10)


def test_create_certificate(client, valid_payload):
    res = client.post("/api/certificates", json=valid_payload)
    assert res.status_code == 201
    cert = res.get_json()["data"]
    assert cert["cert_id"].startswith("CERT-")
    assert cert["status"] == "active"


def test_create_certificate_with_empty_body_fails(client):
    res = client.post("/api/certificates", json={})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_unknown_certificate_returns_404(client):
    res = client.get("/api/certificates/CERT-00000000")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "NOT_FOUND"


def test_signup_logs_you_in(anon_client):
    res = anon_client.post(
        "/api/auth/signup",
        json={"name": "Ada Lovelace", "email": "ada@example.com", "password": "analytical-engine"},
    )
    assert res.status_code == 201
    me = anon_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["data"]["email"] == "ada@example.com"


def test_login_with_wrong_password_fails(client):
    res = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "not-the-password"},
    )
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "UNAUTHORIZED"
