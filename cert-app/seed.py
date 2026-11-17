"""Fill the local database with sample certificates.

Usage:  python seed.py
"""
from datetime import datetime, timezone

from app import create_app
from app.auth import hash_password
from app.db import get_db
from app.helpers import generate_cert_id

DEMO_USER = {"name": "Demo Admin", "email": "demo@example.com", "password": "demo1234"}

SAMPLES = [
    ("Aarav Sharma", "aarav.sharma@example.com", "Python Fundamentals", "2026-01-14", "active"),
    ("Priya Nair", "priya.nair@example.com", "Python Fundamentals", "2026-01-14", "active"),
    ("Rohan Mehta", "rohan.mehta@example.com", "Flask Web Development", "2026-02-03", "active"),
    ("Sneha Iyer", "sneha.iyer@example.com", "Flask Web Development", "2026-02-03", "revoked"),
    ("Vikram Rao", "vikram.rao@example.com", "REST API Design", "2026-02-21", "active"),
    ("Ananya Gupta", "ananya.gupta@example.com", "REST API Design", "2026-02-21", "active"),
    ("Karthik Reddy", "karthik.reddy@example.com", "SQL for Developers", "2026-03-09", "active"),
    ("Meera Pillai", "meera.pillai@example.com", "SQL for Developers", "2026-03-09", "active"),
    ("Arjun Das", "arjun.das@example.com", "Testing with Pytest", "2026-04-17", "active"),
    ("Divya Menon", "divya.menon@example.com", "Testing with Pytest", "2026-04-17", "revoked"),
    ("Siddharth Joshi", "siddharth.joshi@example.com", "Git & GitHub Basics", "2026-05-02", "active"),
    ("Kavya Krishnan", "kavya.krishnan@example.com", "Git & GitHub Basics", "2026-05-02", "active"),
    ("Nikhil Verma", "nikhil.verma@example.com", "Docker Essentials", "2026-06-25", "active"),
    ("Ishita Bose", "ishita.bose@example.com", "Docker Essentials", "2026-06-25", "active"),
    ("Rahul Kulkarni", "rahul.kulkarni@example.com", "Frontend Basics", "2026-08-13", "active"),
]


def main():
    app = create_app()
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM certificates")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for name, email, course, issued, status in SAMPLES:
            db.execute(
                "INSERT INTO certificates "
                "(cert_id, recipient_name, recipient_email, course_name, issue_date, "
                " status, revoked_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    generate_cert_id(),
                    name,
                    email,
                    course,
                    issued,
                    status,
                    now if status == "revoked" else None,
                    now,
                ),
            )

        db.execute("DELETE FROM users WHERE email = ?", (DEMO_USER["email"],))
        db.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (DEMO_USER["name"], DEMO_USER["email"], hash_password(DEMO_USER["password"]), now),
        )
        db.commit()
        print(f"Seeded {len(SAMPLES)} certificates.")
        print(f"Demo login: {DEMO_USER['email']} / {DEMO_USER['password']}")


if __name__ == "__main__":
    main()
