import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS certificates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cert_id         TEXT    NOT NULL UNIQUE,
    recipient_name  TEXT    NOT NULL,
    recipient_email TEXT    NOT NULL,
    course_name     TEXT    NOT NULL,
    issue_date      TEXT    NOT NULL,          -- YYYY-MM-DD
    status          TEXT    NOT NULL DEFAULT 'active',  -- 'active' | 'revoked'
    revoked_at      TEXT,                      -- ISO 8601 UTC timestamp or NULL
    created_at      TEXT    NOT NULL           -- ISO 8601 UTC timestamp
);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,   -- stored in lowercase
    password_hash   TEXT    NOT NULL,
    created_at      TEXT    NOT NULL           -- ISO 8601 UTC timestamp
);
"""


def get_db():
    """Return a SQLite connection for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """Create the tables (if missing) and register the teardown hook."""
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        db.commit()
