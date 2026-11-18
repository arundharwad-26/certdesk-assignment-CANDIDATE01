"""The certificate API.

TODO: build the 5 endpoints below so they match API_CONTRACT.md.
Useful pieces: get_db() in db.py, the helpers in helpers.py, the validation
helpers in validators.py, and login_required in auth.py.
"""
from flask import Blueprint, jsonify, request

from .auth import login_required
from .db import get_db
from .helpers import error_response, generate_cert_id, row_to_dict, utc_now, paginate
from .validators import validate_certificate_payload

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


# 1. Create a certificate

@bp.post("/certificates")
@login_required
def create_certificate():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error_response(
            "BAD_REQUEST",
            "Request body must be a JSON object",
            400,
        )

    cleaned, errors = validate_certificate_payload(data)

    if errors:
        return error_response(
            "VALIDATION_ERROR",
            "Please correct the validation errors",
            400,
            errors,
        )

    db = get_db()

    existing = db.execute(
        """
        SELECT cert_id FROM certificates
        WHERE LOWER(recipient_email) = LOWER(?)
        AND LOWER(course_name) = LOWER(?)
        AND status = 'active'
        """,
        (cleaned["recipient_email"], cleaned["course_name"]),
    ).fetchone()

    if existing:
        return error_response(
            "CONFLICT",
            "An active certificate already exists for this recipient and course",
            409,
        )

    cert_id = generate_cert_id()
    created_at = utc_now()

    db.execute(
        """
        INSERT INTO certificates (
            cert_id, recipient_name, recipient_email,
            course_name, issue_date, status, revoked_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, 'active', NULL, ?)
        """,
        (
            cert_id,
            cleaned["recipient_name"],
            cleaned["recipient_email"],
            cleaned["course_name"],
            cleaned["issue_date"],
            created_at,
        ),
    )

    db.commit()

    certificate = db.execute(
        "SELECT * FROM certificates WHERE cert_id = ?",
        (cert_id,),
    ).fetchone()

    return jsonify({"data": row_to_dict(certificate)}), 201


# 2. List certificates

@bp.get("/certificates")
@login_required
def list_certificates():
    db = get_db()

    page_value = request.args.get("page", "1")
    limit_value = request.args.get("limit", "10")
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip().lower()

    errors = {}

    # Validate page
    try:
        page = int(page_value)
        if page < 1:
            errors["page"] = "Must be a whole number greater than or equal to 1"
    except (ValueError, TypeError):
        errors["page"] = "Must be a valid whole number"

    # Validate limit
    try:
        limit = int(limit_value)
        if not 1 <= limit <= 50:
            errors["limit"] = "Must be between 1 and 50"
    except (ValueError, TypeError):
        errors["limit"] = "Must be a valid whole number"

    # Validate status
    if status and status not in ("active", "revoked"):
        errors["status"] = "Must be either active or revoked"

    if errors:
        return error_response(
            "VALIDATION_ERROR",
            "Invalid query parameters",
            400,
            errors,
        )

    conditions = []
    params = []

    if search:
        conditions.append("LOWER(recipient_name) LIKE LOWER(?)")
        params.append(f"%{search}%")

    if status:
        conditions.append("status = ?")
        params.append(status)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    total = db.execute(
        f"SELECT COUNT(*) FROM certificates {where_clause}",
        params,
    ).fetchone()[0]

    offset, limit = paginate(page, limit)

    rows = db.execute(
        f"""
        SELECT * FROM certificates
        {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()

    certificates = [row_to_dict(row) for row in rows]

    pages = (total + limit - 1) // limit if total else 0

    return jsonify({
        "data": certificates,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": pages,
        },
    }), 200


# 3. Get one certificate

@bp.get("/certificates/<cert_id>")
@login_required
def get_certificate(cert_id):
    db = get_db()

    certificate = db.execute(
        "SELECT * FROM certificates WHERE cert_id = ?",
        (cert_id,),
    ).fetchone()

    if certificate is None:
        return error_response(
            "NOT_FOUND",
            "Certificate not found",
            404,
        )

    return jsonify({"data": row_to_dict(certificate)}), 200


# 4. Verify a certificate (public, no login)
@bp.get("/verify/<cert_id>")
def verify_certificate(cert_id):
    db = get_db()

    certificate = db.execute(
        "SELECT * FROM certificates WHERE cert_id = ?",
        (cert_id,),
    ).fetchone()

    if certificate is None:
        return error_response(
            "NOT_FOUND",
            "Certificate not found",
            404,
        )

    return jsonify({
        "cert_id": certificate["cert_id"],
        "valid": certificate["status"] == "active",
        "status": certificate["status"],
        "recipient_name": certificate["recipient_name"],
        "course_name": certificate["course_name"],
        "issue_date": certificate["issue_date"],
        "revoked_at": certificate["revoked_at"],
    }), 200


# 5. Revoke a certificate
@bp.patch("/certificates/<cert_id>/revoke")
@login_required
def revoke_certificate(cert_id):
    db = get_db()

    certificate = db.execute(
        "SELECT * FROM certificates WHERE cert_id = ?",
        (cert_id,),
    ).fetchone()

    if certificate is None:
        return error_response(
            "NOT_FOUND",
            "Certificate not found",
            404,
        )

    if certificate["status"] == "revoked":
        return error_response(
            "CONFLICT",
            "Certificate has already been revoked",
            409,
        )

    revoked_at = utc_now()

    db.execute(
        """
        UPDATE certificates
        SET status = 'revoked', revoked_at = ?
        WHERE cert_id = ?
        """,
        (revoked_at, cert_id),
    )

    db.commit()

    updated_certificate = db.execute(
        "SELECT * FROM certificates WHERE cert_id = ?",
        (cert_id,),
    ).fetchone()

    return jsonify({
        "data": row_to_dict(updated_certificate)
    }), 200
