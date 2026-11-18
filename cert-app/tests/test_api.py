"""Starter tests. Some of these fail on purpose until you finish the task.

Add your own tests (at least 5) in this file or in new test files.
"""
import smtplib
from unittest.mock import MagicMock, patch

from datetime import date

from app.helpers import paginate, parse_date
from app.db import get_db
from werkzeug.security import check_password_hash

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

def test_verify_certificate_is_public(client, anon_client, valid_payload):
    # Create certificate using logged-in client
    res = client.post("/api/certificates", json=valid_payload)

    assert res.status_code == 201

    cert_id = res.get_json()["data"]["cert_id"]

    # Verify certificate without login
    res = anon_client.get(f"/api/verify/{cert_id}")

    assert res.status_code == 200

    data = res.get_json()

    assert data["valid"] is True
    assert data["status"] == "active"
    assert data["recipient_name"] == valid_payload["recipient_name"]

    # Email must not be exposed publicly
    assert "recipient_email" not in data

def test_revoke_certificate(client, valid_payload):
    # Create a certificate
    res = client.post("/api/certificates", json=valid_payload)

    assert res.status_code == 201

    cert_id = res.get_json()["data"]["cert_id"]

    # Revoke the certificate
    res = client.patch(f"/api/certificates/{cert_id}/revoke")

    assert res.status_code == 200

    data = res.get_json()["data"]

    assert data["status"] == "revoked"
    assert data["revoked_at"] is not None

    # Verify that the revoked certificate is no longer valid
    verify_res = client.get(f"/api/verify/{cert_id}")

    assert verify_res.status_code == 200
    assert verify_res.get_json()["valid"] is False

def test_duplicate_active_certificate_returns_conflict(client, valid_payload):
    # Create the first certificate
    first_res = client.post(
        "/api/certificates",
        json=valid_payload,
    )

    assert first_res.status_code == 201

    # Try creating the same certificate again
    second_res = client.post(
        "/api/certificates",
        json=valid_payload,
    )

    assert second_res.status_code == 409

    data = second_res.get_json()

    assert data["error"]["code"] == "CONFLICT"

def test_reissue_certificate_after_revocation(client, valid_payload):
    # Create the first certificate
    first_res = client.post(
        "/api/certificates",
        json=valid_payload,
    )

    assert first_res.status_code == 201

    first_cert_id = first_res.get_json()["data"]["cert_id"]

    # Revoke the first certificate
    revoke_res = client.patch(
        f"/api/certificates/{first_cert_id}/revoke"
    )

    assert revoke_res.status_code == 200

    # Issue another certificate for the same recipient and course
    second_res = client.post(
        "/api/certificates",
        json=valid_payload,
    )

    assert second_res.status_code == 201

    second_cert_id = second_res.get_json()["data"]["cert_id"]

    assert second_cert_id != first_cert_id
    assert second_res.get_json()["data"]["status"] == "active"

def test_list_certificates_with_pagination(client, valid_payload):
    # Create three certificates with different recipients
    for i in range(3):
        payload = valid_payload.copy()
        payload["recipient_email"] = f"user{i}@example.com"
        payload["recipient_name"] = f"Test User {i}"

        res = client.post("/api/certificates", json=payload)
        assert res.status_code == 201

    # Request the first page with two records
    res = client.get("/api/certificates?page=1&limit=2")

    assert res.status_code == 200

    data = res.get_json()

    assert len(data["data"]) == 2
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["limit"] == 2
    assert data["pagination"]["total"] == 3
    assert data["pagination"]["pages"] == 2

def test_search_certificates_by_recipient_name(client, valid_payload):
    # Create first certificate
    first_payload = valid_payload.copy()
    first_payload["recipient_name"] = "Arun Dharwad"

    res = client.post("/api/certificates", json=first_payload)
    assert res.status_code == 201

    # Create second certificate
    second_payload = valid_payload.copy()
    second_payload["recipient_name"] = "Rahul Kumar"
    second_payload["recipient_email"] = "rahul@example.com"

    res = client.post("/api/certificates", json=second_payload)
    assert res.status_code == 201

    # Search for Arun
    res = client.get("/api/certificates?search=Arun")

    assert res.status_code == 200

    data = res.get_json()["data"]

    assert len(data) == 1
    assert data[0]["recipient_name"] == "Arun Dharwad"

def test_unauthenticated_user_cannot_access_certificates(anon_client):
    res = anon_client.get("/api/certificates")

    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "UNAUTHORIZED"

def test_signup_stores_secure_password_hash(app):
    client = app.test_client()
    password = "secure-password-123"

    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Security Test",
            "email": "security@example.com",
            "password": password,
        },
    )

    assert response.status_code == 201

    with app.app_context():
        user = get_db().execute(
            "SELECT password_hash FROM users WHERE email = ?",
            ("security@example.com",),
        ).fetchone()

        assert user["password_hash"] != password
        assert check_password_hash(user["password_hash"], password)

def test_get_email_settings_returns_null_when_not_configured(client):
    response = client.get("/api/email-settings")

    assert response.status_code == 200
    assert response.get_json() == {"data": None}


def test_get_email_settings_requires_login(anon_client):
    response = anon_client.get("/api/email-settings")

    assert response.status_code == 401

def test_save_email_settings_requires_login(anon_client):
    response = anon_client.put("/api/email-settings", json={})
    assert response.status_code == 401


def test_save_email_settings_rejects_invalid_email(client):
    response = client.put(
        "/api/email-settings",
        json={
            "email": "invalid-email",
            "app_password": "abcdefghijklmnop",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
        },
    )

    assert response.status_code == 400
    assert "email" in response.get_json()["error"]["details"]


def test_save_email_settings_rejects_invalid_port(client):
    response = client.put(
        "/api/email-settings",
        json={
            "email": "academy@example.com",
            "app_password": "abcdefghijklmnop",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 70000,
        },
    )

    assert response.status_code == 400
    assert "smtp_port" in response.get_json()["error"]["details"]

@patch("app.email_settings._connect_smtp")
def test_save_email_settings_encrypts_password(mock_smtp, client, app):
    mock_smtp.return_value = MagicMock()

    payload = {
        "email": "academy@example.com",
        "from_name": "CertDesk Academy",
        "app_password": "abcd efgh ijkl mnop",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
    }

    response = client.put("/api/email-settings", json=payload)

    assert response.status_code == 200

    result = response.get_json()["data"]

    assert result["email"] == "academy@example.com"
    assert result["from_name"] == "CertDesk Academy"
    assert "app_password" not in result

    with app.app_context():
        saved = get_db().execute(
            "SELECT app_password_enc FROM email_settings"
        ).fetchone()

        assert saved is not None
        assert saved["app_password_enc"] != "abcdefghijklmnop"

@patch("app.email_settings._connect_smtp")
def test_send_test_email_success(mock_smtp, client):
    mock_server = MagicMock()
    mock_smtp.return_value = mock_server

    # First, save valid email settings.
    client.put(
        "/api/email-settings",
        json={
            "email": "sender@example.com",
            "from_name": "CertDesk",
            "app_password": "test-app-password",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
        },
    )

    # Then send a test email.
    response = client.post("/api/email-settings/test")

    assert response.status_code == 200
    assert response.get_json()["data"]["sent_to"] == "admin@example.com"
    mock_server.send_message.assert_called_once()

def test_send_test_email_conflict_without_settings(client):
    response = client.post("/api/email-settings/test")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CONFLICT"

@patch("app.email_settings._connect_smtp")
def test_delete_email_settings_success(mock_smtp, client):
    mock_smtp.return_value = MagicMock()

    # Save settings first.
    client.put(
        "/api/email-settings",
        json={
            "email": "sender@example.com",
            "from_name": "CertDesk",
            "app_password": "test-app-password",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
        },
    )

    response = client.delete("/api/email-settings")

    assert response.status_code == 200
    assert response.get_json()["data"]["message"] == (
        "Email settings disconnected successfully"
    )

    # Confirm settings are deleted.
    get_response = client.get("/api/email-settings")
    assert get_response.get_json()["data"] is None

def test_delete_email_settings_not_found(client):
    response = client.delete("/api/email-settings")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"

@patch("app.email_settings._connect_smtp")
def test_send_certificate_email_success(mock_smtp, client):
    mock_server = MagicMock()
    mock_smtp.return_value = mock_server

    # Save SMTP settings.
    client.put(
        "/api/email-settings",
        json={
            "email": "sender@example.com",
            "from_name": "CertDesk",
            "app_password": "test-app-password",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
        },
    )

    # Create a certificate.
    cert_response = client.post(
        "/api/certificates",
        json={
            "recipient_name": "John Doe",
            "recipient_email": "john@example.com",
            "course_name": "Python Programming",
            "issue_date": "2026-11-17",
        },
    )

    cert_id = cert_response.get_json()["data"]["cert_id"]

    # Send certificate email.
    response = client.post(
        f"/api/certificates/{cert_id}/send-email"
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["sent_to"] == "john@example.com"
    mock_server.send_message.assert_called_once()

def test_send_certificate_email_not_found(client):
    response = client.post(
        "/api/certificates/INVALID-CERT/send-email"
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"

def test_send_certificate_email_without_settings(client):
    cert_response = client.post(
        "/api/certificates",
        json={
            "recipient_name": "John Doe",
            "recipient_email": "john@example.com",
            "course_name": "Python Programming",
            "issue_date": "2026-11-17",
        },
    )

    cert_id = cert_response.get_json()["data"]["cert_id"]

    response = client.post(
        f"/api/certificates/{cert_id}/send-email"
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CONFLICT"

@patch("app.email_settings.smtplib.SMTP_SSL")
def test_smtp_465_uses_ssl(mock_smtp_ssl):
    from app.email_settings import _connect_smtp

    mock_server = MagicMock()
    mock_smtp_ssl.return_value = mock_server

    _connect_smtp(
        "smtp.gmail.com",
        465,
        "sender@example.com",
        "test-password",
    )

    mock_smtp_ssl.assert_called_once_with(
        "smtp.gmail.com",
        465,
        timeout=10,
    )
    mock_server.login.assert_called_once_with(
        "sender@example.com",
        "test-password",
    )


@patch("app.email_settings.smtplib.SMTP")
def test_smtp_587_uses_starttls(mock_smtp):
    from app.email_settings import _connect_smtp

    mock_server = MagicMock()
    mock_smtp.return_value = mock_server

    _connect_smtp(
        "smtp.gmail.com",
        587,
        "sender@example.com",
        "test-password",
    )

    mock_smtp.assert_called_once_with(
        "smtp.gmail.com",
        587,
        timeout=10,
    )
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with(
        "sender@example.com",
        "test-password",
    )

@patch(
    "app.email_settings._connect_smtp",
    side_effect=smtplib.SMTPAuthenticationError(
        535, b"Authentication failed"
    ),
)
def test_wrong_app_password_returns_field_error(mock_smtp, client):
    response = client.put(
        "/api/email-settings",
        json={
            "email": "sender@example.com",
            "from_name": "CertDesk",
            "app_password": "wrong-password",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
        },
    )

    assert response.status_code == 400
    assert "app_password" in response.get_json()["error"]["details"]


@patch(
    "app.email_settings._connect_smtp",
    side_effect=OSError("Connection refused"),
)
def test_smtp_connection_error_returns_502(mock_smtp, client):
    response = client.put(
        "/api/email-settings",
        json={
            "email": "sender@example.com",
            "from_name": "CertDesk",
            "app_password": "test-password",
            "smtp_host": "invalid.smtp.server",
            "smtp_port": 587,
        },
    )

    assert response.status_code == 502