import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    yield app


@pytest.fixture
def client(app):
    """A test client that is already logged in."""
    client = app.test_client()
    res = client.post(
        "/api/auth/signup",
        json={"name": "Test Admin", "email": "admin@example.com", "password": "test-password-1"},
    )
    assert res.status_code == 201, res.get_data(as_text=True)
    return client


@pytest.fixture
def anon_client(app):
    """A test client that is NOT logged in."""
    return app.test_client()


@pytest.fixture
def valid_payload():
    return {
        "recipient_name": "Test User",
        "recipient_email": "test.user@example.com",
        "course_name": "Python Fundamentals",
        "issue_date": "2026-03-25",
    }
