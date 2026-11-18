"""Sign-up, login and session handling."""
from werkzeug.security import generate_password_hash, check_password_hash
import functools

from flask import Blueprint, g, jsonify, request, session

from .db import get_db
from .helpers import error_response, utc_now
from .validators import validate_signup_payload

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def hash_password(password):
    """Securely hash a password before storing it."""
    return generate_password_hash(password)
    

def user_to_dict(row):
    """Public shape of a user. Never includes the password."""
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "created_at": row["created_at"],
    }


def _unauthorized(message="Please log in first"):
    return error_response("UNAUTHORIZED", message, 401)


def _start_session(user):
    session.clear()
    session["user_id"] = user["id"]


@auth_bp.before_app_request
def load_logged_in_user():
    """Put the logged-in user (or None) on g.user for every request."""
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = get_db().execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def login_required(view):
    """Only let logged-in users call this endpoint."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
           return _unauthorized()
        return view(*args, **kwargs)

    return wrapped


# Sign up
@auth_bp.post("/signup")
def signup():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request body must be a JSON object", 400)

    cleaned, errors = validate_signup_payload(data)
    if errors:
        return error_response("VALIDATION_ERROR", "Invalid input", 400, errors)

    db = get_db()
    existing = db.execute(
        "SELECT 1 FROM users WHERE email = ?", (cleaned["email"],)
    ).fetchone()
    if existing:
        return error_response("CONFLICT", "An account with this email already exists", 409)

    email = cleaned["email"].lower()
    db.execute(
        "INSERT OR REPLACE INTO users (name, email, password_hash, created_at) "
        "VALUES (?, ?, ?, ?)",
        (cleaned["name"], email, hash_password(cleaned["password"]), utc_now()),
    )
    db.commit()

    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    _start_session(user)
    return jsonify({"data": user_to_dict(user)}), 201


# Log in
@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request body must be a JSON object", 400)

    email = data.get("email")
    password = data.get("password")
    errors = {}
    if not isinstance(email, str) or not email.strip():
        errors["email"] = "This field is required"
    if not isinstance(password, str) or not password:
        errors["password"] = "This field is required"
    if errors:
        return error_response("VALIDATION_ERROR", "Invalid input", 400, errors)

    email = email.strip().lower()
    user = get_db().execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return _unauthorized("Invalid email or password")
    if user is None:
        return _unauthorized("Invalid email or password")

    _start_session(user)
    return jsonify({"data": user_to_dict(user)})


# Log out
@auth_bp.post("/logout")
def logout():
    session.clear()
    return "", 204


# Who am I?
@auth_bp.get("/me")
def me():
    if g.user is None:
        return _unauthorized()
    return jsonify({"data": user_to_dict(g.user)})
