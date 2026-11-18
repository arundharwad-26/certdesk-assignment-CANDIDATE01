"""Email setup (Gmail / SMTP) and emailing certificates to recipients.

TODO (backend task): build these endpoints. The frontend (the "Email setup" tab
and the email option on the Issue form) is already done and calls them.
The exact behaviour is in API_CONTRACT.md, section "Email setup".
"""
import re
import smtplib
import socket
from datetime import datetime, timezone
from email.message import EmailMessage

from cryptography.fernet import Fernet
from flask import Blueprint, current_app, g, jsonify, request

from .auth import login_required
from .db import get_db
from .helpers import error_response
email_bp = Blueprint("email", __name__, url_prefix="/api")

def _encrypt_password(password):
    """Encrypt the SMTP app password before storing it."""
    key = current_app.config.get("EMAIL_ENCRYPTION_KEY")

    if not key:
        raise RuntimeError("EMAIL_ENCRYPTION_KEY is not configured")

    cipher = Fernet(key.encode("utf-8"))
    return cipher.encrypt(password.encode("utf-8")).decode("utf-8")


def _decrypt_password(encrypted_password):
    """Decrypt the SMTP app password when needed for authentication."""
    key = current_app.config.get("EMAIL_ENCRYPTION_KEY")

    if not key:
        raise RuntimeError("EMAIL_ENCRYPTION_KEY is not configured")

    cipher = Fernet(key.encode("utf-8"))
    return cipher.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")

def _connect_smtp(host, port, email, password):
    """Connect to SMTP and authenticate using SSL or STARTTLS."""
    server = None

    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(email, password)
        return server

    except Exception:
        if server is not None:
            try:
                server.quit()
            except Exception:
                server.close()
        raise

def _validate_email_settings(data, user_name):
    """Validate and clean the email settings request."""
    errors = {}
    cleaned = {}

    # Sender name is optional.
    from_name = data.get("from_name", "")
    if from_name is None:
        from_name = ""

    if not isinstance(from_name, str):
        errors["from_name"] = "Must be a string"
    elif len(from_name.strip()) > 100:
        errors["from_name"] = "Must not exceed 100 characters"
    else:
        cleaned["from_name"] = from_name.strip() or user_name

    # Sender email.
    email = data.get("email")
    if not isinstance(email, str) or not email.strip():
        errors["email"] = "This field is required"
    else:
        email = email.strip().lower()
        if len(email) > 254 or not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", email
        ):
            errors["email"] = "Must be a valid email address"
        else:
            cleaned["email"] = email

    # Gmail app password.
    password = data.get("app_password")
    if not isinstance(password, str):
        errors["app_password"] = "This field is required"
    else:
        password = password.replace(" ", "")
        if not 1 <= len(password) <= 128:
            errors["app_password"] = (
                "Must contain between 1 and 128 characters after removing spaces"
            )
        else:
            cleaned["app_password"] = password

    # SMTP hostname.
    host = data.get("smtp_host")
    if not isinstance(host, str) or not host.strip():
        errors["smtp_host"] = "This field is required"
    else:
        host = host.strip()
        if not re.fullmatch(
            r"(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*",
            host,
        ):
            errors["smtp_host"] = "Must be a valid hostname"
        else:
            cleaned["smtp_host"] = host

    # SMTP port.
    port = data.get("smtp_port")
    if isinstance(port, bool) or not isinstance(port, int):
        errors["smtp_port"] = "Must be an integer"
    elif not 1 <= port <= 65535:
        errors["smtp_port"] = "Must be between 1 and 65535"
    else:
        cleaned["smtp_port"] = port

    return cleaned, errors

def _not_implemented():
    return error_response("NOT_IMPLEMENTED", "Email setup is not built yet", 501)


# E1. Get my email settings
@email_bp.get("/email-settings")
@login_required
def get_email_settings():
    from flask import g, jsonify
    from .db import get_db

    settings = get_db().execute(
        """
        SELECT email, from_name, smtp_host, smtp_port, verified_at
        FROM email_settings
        WHERE user_id = ?
        """,
        (g.user["id"],),
    ).fetchone()

    if settings is None:
        return jsonify({"data": None}), 200

    return jsonify({"data": dict(settings)}), 200

# E2. Save (and verify) email settings
@email_bp.put("/email-settings")
@login_required
def save_email_settings():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error_response(
            "VALIDATION_ERROR",
            "Request body must be a JSON object",
            400,
        )

    cleaned, errors = _validate_email_settings(
        data, g.user["name"]
    )

    if errors:
        return error_response(
            "VALIDATION_ERROR",
            "Please correct the invalid fields",
            400,
            errors,
        )

    # Verify SMTP credentials before saving.
    server = None

    try:
        server = _connect_smtp(
            cleaned["smtp_host"],
            cleaned["smtp_port"],
            cleaned["email"],
            cleaned["app_password"],
        )

    except smtplib.SMTPAuthenticationError:
        return error_response(
            "VALIDATION_ERROR",
            "Gmail rejected the email or app password",
            400,
            {
                "app_password":
                    "Gmail did not accept this email and app password"
            },
        )

    except (smtplib.SMTPException, OSError, socket.timeout) as exc:
        return error_response(
            "SMTP_ERROR",
            f"Could not connect to SMTP server: {exc}",
            502,
        )

    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass

    # Encrypt the password only after successful SMTP verification.
    encrypted_password = _encrypt_password(cleaned["app_password"])

    verified_at = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    db = get_db()

    db.execute(
        """
        INSERT INTO email_settings (
            user_id, email, from_name, smtp_host,
            smtp_port, app_password_enc, verified_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            email = excluded.email,
            from_name = excluded.from_name,
            smtp_host = excluded.smtp_host,
            smtp_port = excluded.smtp_port,
            app_password_enc = excluded.app_password_enc,
            verified_at = excluded.verified_at
        """,
        (
            g.user["id"],
            cleaned["email"],
            cleaned["from_name"],
            cleaned["smtp_host"],
            cleaned["smtp_port"],
            encrypted_password,
            verified_at,
        ),
    )

    db.commit()

    return jsonify({
        "data": {
            "email": cleaned["email"],
            "from_name": cleaned["from_name"],
            "smtp_host": cleaned["smtp_host"],
            "smtp_port": cleaned["smtp_port"],
            "verified_at": verified_at,
        }
    }), 200


# E3. Send a test email
@email_bp.post("/email-settings/test")
@login_required
def send_test_email():
    settings = get_db().execute(
        """
        SELECT email, from_name, smtp_host, smtp_port, app_password_enc
        FROM email_settings
        WHERE user_id = ?
        """,
        (g.user["id"],),
    ).fetchone()

    if settings is None:
        return error_response(
            "CONFLICT",
            "Email settings are not configured",
            409,
        )

    password = _decrypt_password(settings["app_password_enc"])
    server = None

    try:
        server = _connect_smtp(
            settings["smtp_host"],
            settings["smtp_port"],
            settings["email"],
            password,
        )

        message = EmailMessage()
        message["Subject"] = "CertDesk Test Email"
        message["From"] = (
            f'{settings["from_name"]} <{settings["email"]}>'
        )
        message["To"] = g.user["email"]
        message.set_content(
            "This is a test email from CertDesk. "
            "Your email settings are working correctly."
        )

        server.send_message(message)

        return jsonify({
            "data": {
                "sent_to": g.user["email"],
            }
        }), 200

    except Exception:
        return error_response(
            "SMTP_ERROR",
            "Failed to send test email",
            502,
        )

    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


# E4. Disconnect
@email_bp.delete("/email-settings")
@login_required
def delete_email_settings():
    db = get_db()

    cursor = db.execute(
        """
        DELETE FROM email_settings
        WHERE user_id = ?
        """,
        (g.user["id"],),
    )
    db.commit()

    if cursor.rowcount == 0:
        return error_response(
            "NOT_FOUND",
            "Email settings are not configured",
            404,
        )

    return jsonify({
        "data": {
            "message": "Email settings disconnected successfully"
        }
    }), 200

# E5. Email a certificate to its recipient
@email_bp.post("/certificates/<cert_id>/send-email")
@login_required
def send_certificate_email(cert_id):
    db = get_db()

    # Step 1: Find the certificate.
    certificate = db.execute(
        """
        SELECT cert_id, recipient_name, recipient_email,
               course_name, issue_date, status
        FROM certificates
        WHERE cert_id = ?
        """,
        (cert_id,),
    ).fetchone()

    if certificate is None:
        return error_response(
            "NOT_FOUND",
            "Certificate not found",
            404,
        )

    # Step 2: Get the logged-in user's email settings.
    settings = db.execute(
        """
        SELECT email, from_name, smtp_host,
               smtp_port, app_password_enc
        FROM email_settings
        WHERE user_id = ?
        """,
        (g.user["id"],),
    ).fetchone()

    if settings is None:
        return error_response(
            "CONFLICT",
            "Email settings are not configured",
            409,
        )

    # Step 3: Decrypt the saved SMTP password.
    password = _decrypt_password(settings["app_password_enc"])
    server = None

    try:
        # Step 4: Connect to SMTP.
        server = _connect_smtp(
            settings["smtp_host"],
            settings["smtp_port"],
            settings["email"],
            password,
        )

        # Step 5: Prepare the certificate email.
        message = EmailMessage()
        message["Subject"] = (
            f'Your Certificate - {certificate["course_name"]}'
        )
        message["From"] = (
            f'{settings["from_name"]} <{settings["email"]}>'
        )
        message["To"] = certificate["recipient_email"]

        message.set_content(
            f"""
Hello {certificate["recipient_name"]},

Congratulations!

Your certificate has been issued successfully.

Certificate Details:

Certificate ID: {certificate["cert_id"]}
Recipient Name: {certificate["recipient_name"]}
Course Name: {certificate["course_name"]}
Issue Date: {certificate["issue_date"]}
Status: {certificate["status"].upper()}

Thank you,
{settings["from_name"]}
"""
        )

        # Step 6: Send the email.
        server.send_message(message)

        return jsonify({
            "data": {
                "message": "Certificate email sent successfully",
                "cert_id": certificate["cert_id"],
                "sent_to": certificate["recipient_email"],
            }
        }), 200

    except Exception:
        return error_response(
            "SMTP_ERROR",
            "Failed to send certificate email",
            502,
        )

    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass
