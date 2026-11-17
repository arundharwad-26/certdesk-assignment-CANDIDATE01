"""Email setup (Gmail / SMTP) and emailing certificates to recipients.

TODO (backend task): build these endpoints. The frontend (the "Email setup" tab
and the email option on the Issue form) is already done and calls them.
The exact behaviour is in API_CONTRACT.md, section "Email setup".
"""
from flask import Blueprint

from .auth import login_required
from .helpers import error_response

email_bp = Blueprint("email", __name__, url_prefix="/api")


def _not_implemented():
    return error_response("NOT_IMPLEMENTED", "Email setup is not built yet", 501)


# E1. Get my email settings
@email_bp.get("/email-settings")
@login_required
def get_email_settings():
    return _not_implemented()


# E2. Save (and verify) email settings
@email_bp.put("/email-settings")
@login_required
def save_email_settings():
    return _not_implemented()


# E3. Send a test email
@email_bp.post("/email-settings/test")
@login_required
def send_test_email():
    return _not_implemented()


# E4. Disconnect
@email_bp.delete("/email-settings")
@login_required
def delete_email_settings():
    return _not_implemented()


# E5. Email a certificate to its recipient
@email_bp.post("/certificates/<cert_id>/send-email")
@login_required
def send_certificate_email(cert_id):
    return _not_implemented()
