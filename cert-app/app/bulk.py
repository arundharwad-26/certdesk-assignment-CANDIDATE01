import csv
import io
import json
import threading
from .auth import login_required

from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, g, jsonify, request         

from .db import get_db
from .helpers import error_response, generate_cert_id, utc_now
from .validators import validate_certificate_payload
from email.message import EmailMessage
from .email_settings import _connect_smtp, _decrypt_password

bulk_bp = Blueprint("bulk", __name__, url_prefix="/api")

MAX_FILE_SIZE = 1024 * 1024  # 1 MB
MAX_ROWS = 500

REQUIRED_COLUMNS = {
    "recipient_name",
    "recipient_email",
    "course_name",
    "issue_date",
}


def validate_csv_file(file):
    """Read a CSV file and return validated preview rows."""

    if file is None or not file.filename:
        return None, error_response(
            "VALIDATION_ERROR",
            "Please upload a CSV file",
            400,
        )

    file_bytes = file.read(MAX_FILE_SIZE + 1)

    if len(file_bytes) > MAX_FILE_SIZE:
        return None, error_response(
            "VALIDATION_ERROR",
            "CSV file must not exceed 1 MB",
            400,
        )

    try:
        content = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, error_response(
            "VALIDATION_ERROR",
            "CSV file must use UTF-8 encoding",
            400,
        )

    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames:
        return None, error_response(
            "VALIDATION_ERROR",
            "CSV file must contain a header row",
            400,
        )

    headers = [header.strip() for header in reader.fieldnames if header]

    headers = [(header or "").strip() for header in reader.fieldnames]

    if any(not header for header in headers):
        return None, error_response(
            "VALIDATION_ERROR",
            "CSV contains an empty column name",
            400,
        )

    if len(headers) != len(set(headers)):
        return None, error_response(
            "VALIDATION_ERROR",
            "CSV contains duplicate column names",
            400,
        )

    # Make DictReader use the cleaned header names.
    reader.fieldnames = headers

    if not REQUIRED_COLUMNS.issubset(set(headers)):
        missing = sorted(REQUIRED_COLUMNS - set(headers))
        return None, error_response(
            "VALIDATION_ERROR",
            "CSV is missing required columns",
            400,
            {"columns": f"Missing: {', '.join(missing)}"},
        )
    rows = []
    seen = set()

    db = get_db()

    for row_number, raw_row in enumerate(reader, start=2):
        if not raw_row or not any(
            str(value or "").strip() for value in raw_row.values()
        ):
            continue

        if len(rows) >= MAX_ROWS:
            return None, error_response(
                "VALIDATION_ERROR",
                "CSV must not contain more than 500 data rows",
                400,
            )

        data = {
            field: (raw_row.get(field) or "").strip()
            for field in REQUIRED_COLUMNS
        }

        cleaned, errors = validate_certificate_payload(data)

        status = "ready" if not errors else "error"

        if status == "ready":
            duplicate_key = (
                cleaned["recipient_email"].lower(),
                cleaned["course_name"].lower(),
            )

            if duplicate_key in seen:
                errors["duplicate"] = (
                    "Duplicate recipient and course in this CSV file"
                )
                status = "error"
            else:
                seen.add(duplicate_key)

            if status == "ready":
                existing = db.execute(
                    """
                    SELECT cert_id FROM certificates
                    WHERE LOWER(recipient_email) = LOWER(?)
                    AND LOWER(course_name) = LOWER(?)
                    AND status = 'active'
                    """,
                    (
                        cleaned["recipient_email"],
                        cleaned["course_name"],
                    ),
                ).fetchone()

                if existing:
                    errors["duplicate"] = (
                        "An active certificate already exists "
                        "for this recipient and course"
                    )
                    status = "error"

        rows.append({
            "row_number": row_number,
            "data": cleaned if cleaned else data,
            "status": status,
            "errors": errors,
        })

    if not rows:
        return None, error_response(
            "VALIDATION_ERROR",
            "CSV contains no data rows",
            400,
        )

    return rows, None
@bulk_bp.post("/bulk-issues")
@login_required
def upload_bulk_csv():
    file = request.files.get("file")

    rows, error = validate_csv_file(file)

    if error:
        return error

    db = get_db()
    now = utc_now()

    ready_rows = sum(1 for row in rows if row["status"] == "ready")
    error_rows = len(rows) - ready_rows

    cursor = db.execute(
        """
        INSERT INTO bulk_jobs (
            user_id, filename, status,
            total_rows, ready_rows, error_rows,
            processed_rows, created_at, updated_at
        )
        VALUES (?, ?, 'preview', ?, ?, ?, 0, ?, ?)
        """,
        (
            g.user["id"],
            file.filename,
            len(rows),
            ready_rows,
            error_rows,
            now,
            now,
        ),
    )

    job_id = cursor.lastrowid

    for row in rows:
        data = row["data"]

        db.execute(
            """
            INSERT INTO bulk_job_rows (
                job_id, row_number,
                recipient_name, recipient_email,
                course_name, issue_date,
                status, errors, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                row["row_number"],
                data.get("recipient_name"),
                data.get("recipient_email"),
                data.get("course_name"),
                data.get("issue_date"),
                row["status"],
                json.dumps(row["errors"]),
                now,
            ),
        )

    db.commit()

    return jsonify({
        "data": {
            "job_id": job_id,
            "filename": file.filename,
            "status": "preview",
            "total_rows": len(rows),
            "ready_rows": ready_rows,
            "error_rows": error_rows,
            "rows": rows,
        }
    }), 201


def process_bulk_job(app, job_id):
    """Issue valid certificates and email recipients when configured."""

    with app.app_context():
        db = get_db()

        job = db.execute(
            "SELECT id, user_id FROM bulk_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

        if job is None:
            return

        # Get the email settings belonging to the job owner.
        settings = db.execute(
            """
            SELECT email, from_name, smtp_host,
                   smtp_port, app_password_enc
            FROM email_settings
            WHERE user_id = ?
            """,
            (job["user_id"],),
        ).fetchone()

        rows = db.execute(
            """
            SELECT * FROM bulk_job_rows
            WHERE job_id = ? AND status = 'ready'
            ORDER BY row_number
            """,
            (job_id,),
        ).fetchall()

        for row in rows:
            cert_id = None
            row_status = "issued"
            errors = {}

            try:
                # Recheck duplicates before issuing.
                existing = db.execute(
                    """
                    SELECT cert_id FROM certificates
                    WHERE LOWER(recipient_email) = LOWER(?)
                    AND LOWER(course_name) = LOWER(?)
                    AND status = 'active'
                    """,
                    (row["recipient_email"], row["course_name"]),
                ).fetchone()

                if existing:
                    row_status = "error"
                    errors["duplicate"] = (
                        "An active certificate already exists "
                        "for this recipient and course"
                    )
                else:
                    cert_id = generate_cert_id()

                    db.execute(
                        """
                        INSERT INTO certificates (
                            cert_id, recipient_name, recipient_email,
                            course_name, issue_date, status,
                            revoked_at, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, 'active', NULL, ?)
                        """,
                        (
                            cert_id,
                            row["recipient_name"],
                            row["recipient_email"],
                            row["course_name"],
                            row["issue_date"],
                            utc_now(),
                        ),
                    )

                    # Commit certificate before attempting email.
                    db.commit()

            except Exception:
                db.rollback()
                cert_id = None
                row_status = "error"
                errors["processing"] = (
                    "Certificate could not be issued due to a processing error"
                )

            # Send email only after successful certificate issuance.
            if cert_id is not None and settings is not None:
                server = None

                try:
                    password = _decrypt_password(
                        settings["app_password_enc"]
                    )

                    server = _connect_smtp(
                        settings["smtp_host"],
                        settings["smtp_port"],
                        settings["email"],
                        password,
                    )

                    message = EmailMessage()
                    message["Subject"] = (
                        f'Your Certificate - {row["course_name"]}'
                    )
                    message["From"] = (
                        f'{settings["from_name"]} <{settings["email"]}>'
                    )
                    message["To"] = row["recipient_email"]

                    message.set_content(
                        f"""Hello {row["recipient_name"]},

Congratulations!

Your certificate has been issued successfully.

Certificate Details:

Certificate ID: {cert_id}
Recipient Name: {row["recipient_name"]}
Course Name: {row["course_name"]}
Issue Date: {row["issue_date"]}
Status: ACTIVE

You can verify your certificate using its Certificate ID.

Thank you,
{settings["from_name"]}
"""
                    )

                    server.send_message(message)

                except Exception:
                    # Email failure must not undo certificate issuance.
                    errors["email"] = (
                        "Certificate was issued, but the email could not be sent"
                    )

                finally:
                    if server is not None:
                        try:
                            server.quit()
                        except Exception:
                            pass

            # Save the final row status and any processing/email errors.
            db.execute(
                """
                UPDATE bulk_job_rows
                SET status = ?, errors = ?, cert_id = ?
                WHERE id = ?
                """,
                (
                    row_status,
                    json.dumps(errors),
                    cert_id,
                    row["id"],
                ),
            )

            db.execute(
                """
                UPDATE bulk_jobs
                SET processed_rows = processed_rows + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (utc_now(), job_id),
            )

            db.commit()

        # Recalculate errors, including duplicates discovered during processing.
        error_count = db.execute(
            """
            SELECT COUNT(*) AS total
            FROM bulk_job_rows
            WHERE job_id = ? AND status = 'error'
            """,
            (job_id,),
        ).fetchone()["total"]

        db.execute(
            """
            UPDATE bulk_jobs
            SET status = 'completed',
                error_rows = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (error_count, utc_now(), job_id),
        )
        db.commit()


@bulk_bp.post("/bulk-issues/<int:job_id>/approve")
@login_required
def approve_bulk_job(job_id):
    db = get_db()

    job = db.execute(
        """
        SELECT * FROM bulk_jobs
        WHERE id = ? AND user_id = ?
        """,
        (job_id, g.user["id"]),
    ).fetchone()

    if job is None:
        return error_response(
            "NOT_FOUND",
            "Bulk job not found",
            404,
        )

    if job["status"] != "preview":
        return error_response(
            "CONFLICT",
            "This bulk job has already been approved or processed",
            409,
        )

    if job["ready_rows"] == 0:
        return error_response(
            "VALIDATION_ERROR",
            "There are no valid rows to approve",
            400,
        )

    # Atomic update prevents approving the same job twice.
    cursor = db.execute(
        """
        UPDATE bulk_jobs
        SET status = 'processing', updated_at = ?
        WHERE id = ? AND user_id = ? AND status = 'preview'
        """,
        (utc_now(), job_id, g.user["id"]),
    )

    if cursor.rowcount != 1:
        db.rollback()
        return error_response(
            "CONFLICT",
            "This bulk job has already been approved",
            409,
        )

    db.commit()

    app = current_app._get_current_object()

    if app.config.get("BULK_RUN_SYNCHRONOUSLY", False):
        # Useful for predictable automated tests.
        process_bulk_job(app, job_id)
    else:
        worker = threading.Thread(
            target=process_bulk_job,
            args=(app, job_id),
            daemon=True,
        )
        worker.start()

    return jsonify({
        "data": {
            "job_id": job_id,
            "status": "processing",
            "message": "Bulk certificate processing started",
        }
    }), 202


@bulk_bp.get("/bulk-issues/<int:job_id>")
@login_required
def get_bulk_job(job_id):
    db = get_db()

    job = db.execute(
        """
        SELECT * FROM bulk_jobs
        WHERE id = ? AND user_id = ?
        """,
        (job_id, g.user["id"]),
    ).fetchone()

    if job is None:
        return error_response(
            "NOT_FOUND",
            "Bulk job not found",
            404,
        )

    rows = db.execute(
        """
        SELECT row_number, recipient_name, recipient_email,
               course_name, issue_date, status, errors, cert_id
        FROM bulk_job_rows
        WHERE job_id = ?
        ORDER BY row_number
        """,
        (job_id,),
    ).fetchall()

    return jsonify({
        "data": {
            "job_id": job["id"],
            "filename": job["filename"],
            "status": job["status"],
            "total_rows": job["total_rows"],
            "ready_rows": job["ready_rows"],
            "error_rows": job["error_rows"],
            "processed_rows": job["processed_rows"],
            "rows": [
                {
                    "row_number": row["row_number"],
                    "recipient_name": row["recipient_name"],
                    "recipient_email": row["recipient_email"],
                    "course_name": row["course_name"],
                    "issue_date": row["issue_date"],
                    "status": row["status"],
                    "errors": json.loads(row["errors"]),
                    "cert_id": row["cert_id"],
                }
                for row in rows
            ],
        }
    }), 200


@bulk_bp.get("/bulk-issues/<int:job_id>/results.csv")
@login_required
def download_bulk_results(job_id):
    db = get_db()

    job = db.execute(
        """
        SELECT id, filename FROM bulk_jobs
        WHERE id = ? AND user_id = ?
        """,
        (job_id, g.user["id"]),
    ).fetchone()

    if job is None:
        return error_response(
            "NOT_FOUND",
            "Bulk job not found",
            404,
        )

    rows = db.execute(
        """
        SELECT row_number, recipient_name, recipient_email,
               course_name, issue_date, status, errors, cert_id
        FROM bulk_job_rows
        WHERE job_id = ?
        ORDER BY row_number
        """,
        (job_id,),
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "row_number",
        "recipient_name",
        "recipient_email",
        "course_name",
        "issue_date",
        "status",
        "errors",
        "cert_id",
    ])

    for row in rows:
        writer.writerow([
            row["row_number"],
            row["recipient_name"],
            row["recipient_email"],
            row["course_name"],
            row["issue_date"],
            row["status"],
            row["errors"],
            row["cert_id"] or "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="bulk-job-{job_id}-results.csv"'
        },
    )
