import re
from datetime import date
from .helpers import parse_date
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128


def _text(data, field, min_len, max_len, errors, cleaned):
    value = data.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        errors[field] = "This field is required"
        return
    if not isinstance(value, str):
        errors[field] = "Must be a string"
        return
    value = value.strip()
    if not min_len <= len(value) <= max_len:
        errors[field] = f"Must be between {min_len} and {max_len} characters"
        return
    cleaned[field] = value


def _email(data, field, errors, cleaned):
    """Required, trimmed, and in a valid email format."""
    _text(data, field, 3, 254, errors, cleaned)
    if field in cleaned and not EMAIL_RE.match(cleaned[field]):
        errors[field] = "Must be a valid email address"
        del cleaned[field]


def validate_signup_payload(data):
    """Return (cleaned_data, errors) for the sign-up form."""
    errors, cleaned = {}, {}

    _text(data, "name", 2, 100, errors, cleaned)
    _email(data, "email", errors, cleaned)

    password = data.get("password")
    if password is None or password == "":
        errors["password"] = "This field is required"
    elif not isinstance(password, str):
        errors["password"] = "Must be a string"
    elif not PASSWORD_MIN_LEN <= len(password) <= PASSWORD_MAX_LEN:
        errors["password"] = (
            f"Must be between {PASSWORD_MIN_LEN} and {PASSWORD_MAX_LEN} characters"
        )
    else:
        # Not trimmed on purpose: spaces are allowed in passwords.
        cleaned["password"] = password

    return cleaned, errors


def validate_certificate_payload(data):
    errors, cleaned = {}, {}

    _text(data, "recipient_name", 2, 100, errors, cleaned)
    _email(data, "recipient_email", errors, cleaned)
    _text(data, "course_name", 2, 150, errors, cleaned)

    issue_date = data.get("issue_date")

    if issue_date is None or issue_date == "":
        errors["issue_date"] = "This field is required"
    elif not isinstance(issue_date, str):
        errors["issue_date"] = "Must be a string"
    else:
        issue_date = issue_date.strip()

        try:
            parsed_date = parse_date(issue_date)

            if parsed_date > date.today():
                errors["issue_date"] = "Issue date cannot be in the future"
            else:
                cleaned["issue_date"] = issue_date

        except ValueError:
            errors["issue_date"] = "Must be a valid date in YYYY-MM-DD format"

    if "recipient_email" in cleaned:
        cleaned["recipient_email"] = cleaned["recipient_email"].lower()

    return cleaned, errors
