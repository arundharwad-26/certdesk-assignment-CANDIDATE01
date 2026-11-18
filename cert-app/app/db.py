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

CREATE TABLE IF NOT EXISTS email_settings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL UNIQUE,
    email           TEXT NOT NULL,
    from_name       TEXT NOT NULL,
    smtp_host       TEXT NOT NULL,
    smtp_port       INTEGER NOT NULL,
    app_password_enc TEXT NOT NULL,
    verified_at     TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS bulk_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    filename        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'preview',
    total_rows      INTEGER NOT NULL DEFAULT 0,
    ready_rows      INTEGER NOT NULL DEFAULT 0,
    error_rows      INTEGER NOT NULL DEFAULT 0,
    processed_rows  INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bulk_job_rows (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL,
    row_number      INTEGER NOT NULL,
    recipient_name  TEXT,
    recipient_email TEXT,
    course_name     TEXT,
    issue_date      TEXT,
    status          TEXT NOT NULL DEFAULT 'error',
    errors          TEXT NOT NULL DEFAULT '[]',
    cert_id         TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES bulk_jobs(id) ON DELETE CASCADE,
    UNIQUE (job_id, row_number)
);

CREATE INDEX IF NOT EXISTS idx_bulk_jobs_user
ON bulk_jobs(user_id);

CREATE INDEX IF NOT EXISTS idx_bulk_job_rows_job
ON bulk_job_rows(job_id);
"""
def get_db():
    """Return a SQLite connection for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
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
