"""The certificate API.

TODO: build the 5 endpoints below so they match API_CONTRACT.md.
Useful pieces: get_db() in db.py, the helpers in helpers.py, the validation
helpers in validators.py, and login_required in auth.py.
"""
from flask import Blueprint, jsonify

from .auth import login_required
from .helpers import error_response

bp = Blueprint("api", __name__, url_prefix="/api")


def _not_implemented():
    return error_response("NOT_IMPLEMENTED", "This endpoint is not built yet", 501)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


# 1. Create a certificate
@bp.post("/certificates")
@login_required
def create_certificate():
    return _not_implemented()


# 2. List certificates
@bp.get("/certificates")
@login_required
def list_certificates():
    return _not_implemented()


# 3. Get one certificate
@bp.get("/certificates/<cert_id>")
@login_required
def get_certificate(cert_id):
    return _not_implemented()


# 4. Verify a certificate (public, no login)
@bp.get("/verify/<cert_id>")
def verify_certificate(cert_id):
    return _not_implemented()


# 5. Revoke a certificate
@bp.patch("/certificates/<cert_id>/revoke")
@login_required
def revoke_certificate(cert_id):
    return _not_implemented()
