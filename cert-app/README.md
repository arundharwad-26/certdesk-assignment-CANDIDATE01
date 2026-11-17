# CertDesk: Backend Developer Intern Assignment

Thanks for applying! This assignment is a small, realistic piece of work like the work you'd do with us. Read this whole document before you start.

**Deadline:** 26 hours from when you receive this assignment.
**Expected effort:** about **4–5 hours**. We don't expect perfection. If you run out of time, say what you would have done next in `NOTES.md`.

---

## The app

**CertDesk** is a small web app to issue course certificates and let anyone check whether a certificate is real. Users sign up, log in, issue certificates, revoke them, verify them, and email them to the people who earned them.

| Part | Status |
|---|---|
| Frontend: login, sign-up, certificates list, issue form, verify, email setup | Built |
| Backend: login, sign-up and sessions (`app/auth.py`) | Built |
| Database connection, helpers, starter tests | Built |
| Backend: the certificate API | **You build it** (Task 1) |
| Bugs in the code we give you | **You fix them** (Task 2) |
| Backend: email setup | **You build it** (Task 3) |
| Bulk issue: frontend and backend | **You build it** (Task 4) |
| Tests and `NOTES.md` | **You write them** (Tasks 5 and 6) |

The exact API the frontend expects is described in **[`API_CONTRACT.md`](API_CONTRACT.md)**. Read it carefully: it is the spec.

### Tech rules

- Write all backend code in **Python 3.10+** with **Flask 3**.
- Use **SQLite** through Python's built-in `sqlite3` module. Don't add an ORM (such as SQLAlchemy) or other big frameworks.
- Use **pytest** for tests.
- Send email with Python's built-in `smtplib`.
- For background work, Python's standard library (for example `threading` or `concurrent.futures`) is enough. You don't need Celery, Redis or a message queue.
- The frontend is plain HTML, CSS and JavaScript with no build step. Keep it that way, and match the existing look.
- Small extra libraries are fine if you explain why in `NOTES.md`.

---

## Get the code

1. **Fork** this repository to your own GitHub account: click **Fork** at the top right of the repository page.
2. **Clone your fork**, not this repository, and do all your work in your fork.
3. Push only to your fork. **Don't push to this repository, and don't open pull requests to it.**

```bash
git clone https://github.com/<your-username>/<your-fork>.git
cd <your-fork>
```

---

## Setup

```bash
cd cert-app
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python seed.py                    # loads 15 sample certificates + a demo account
python run.py                     # open http://localhost:5000
```

Log in with the demo account **`demo@example.com` / `demo1234`**, or create your own on the sign-up page.

Run tests:

```bash
pytest -v
```

Some starter tests **fail on purpose** right now. They must all pass when you are done.

---

## Project layout

```
app/
  __init__.py        # app factory, serves the pages, JSON error handlers
  auth.py            # sign-up, login, logout, sessions, login_required
  db.py              # SQLite connection + table schema
  helpers.py         # small shared helpers
  validators.py      # input validation
  routes.py          # <-- Task 1: the certificate API
  email_settings.py  # <-- Task 3: the email setup API
frontend/
  login.html, login.js       # login page
  signup.html, signup.js     # sign-up page
  index.html, app.js         # the main app (after login)  <-- Task 4: bulk issue screens
  common.js, style.css       # shared helpers and styles
tests/               # pytest tests (the `client` fixture is already logged in)
seed.py              # sample data
API_CONTRACT.md      # the spec
NOTES.md             # <-- Task 6: create and fill this in
```

---

## Your tasks

### Task 1: Build the certificate API

The 5 certificate endpoints in `app/routes.py` return `501 Not Implemented`. Build them so they match `API_CONTRACT.md` exactly:

1. `POST /api/certificates`: create (validation + duplicate rule)
2. `GET /api/certificates`: list (paging, search, status filter)
3. `GET /api/certificates/<cert_id>`: get one
4. `GET /api/verify/<cert_id>`: public verify, no login needed
5. `PATCH /api/certificates/<cert_id>/revoke`: revoke

Pay attention to status codes, the error format, the validation rules (report **all** failing fields at once), and which endpoints need a login. Use parameterised SQL.

### Task 2: Find and fix the bugs

The code we give you has **several bugs**. They can be anywhere: in the backend or the frontend, in code you build on or in code that already runs. Some of them are serious. **Find them and fix all of them.**

- The bugs are in the code, **not** in `API_CONTRACT.md` or the tests. Don't change the contract or the starter tests to make a bug go away.
- For each bug, write in `NOTES.md`: what the bug was, how you found it, how you fixed it, and what could go wrong if it stayed.
- Where you can, add a test that would fail if the bug came back.

Tip: run the app and use every screen like a real user would. Read the code that is already there, not only the code you write.

### Task 3: Email setup (backend)

The **Email setup** tab is already built. A user enters their Gmail address, a Google app password, the SMTP server and the port, so that certificates are emailed to recipients from that address. The endpoints in `app/email_settings.py` return `501` right now, so the app always says "Email isn't set up".

> **User story:** As a CertDesk user, I want to connect my Gmail account once, so that every certificate I issue is emailed to its recipient from my own address.

Build the 5 endpoints in `app/email_settings.py` so they match the **Email setup** section of `API_CONTRACT.md`: get settings, save settings, send a test email, disconnect, and email a certificate.

It is done when:

- Before saving, the server **signs in to the SMTP server** with the given details, and saves only if that works. A wrong app password shows as an error under the app password field. A wrong server or port returns `502`.
- Port `465` uses SSL; other ports use STARTTLS. Use a timeout (about 10 seconds) so a bad server doesn't hang the request.
- Each user has their own settings.
- The app password is **never** returned by any endpoint. Decide how to store it safely, and explain your choice in `NOTES.md`.
- When a certificate is issued and email is set up, the recipient gets an email from the configured address with their name, the course, the issue date, the certificate ID, and how to verify it.
- A failed email never undoes an issued certificate.
- Tests never send real emails: mock `smtplib.SMTP` and `smtplib.SMTP_SSL`.

To try it for real, you need a Gmail account with **2-Step Verification** turned on and an **app password** (Google Account → Security → App passwords). The Email setup tab explains the steps.

### Task 4: Bulk issue (new feature: frontend and backend)

Today certificates are issued one at a time, but a trainer usually needs certificates for a whole class. Build **Bulk issue**: the user uploads a CSV file, checks it, approves it, and CertDesk issues all the certificates **in the background**.

> **User story:** As a CertDesk user, I want to upload a CSV file of recipients, check it and approve it, so that everyone gets their certificate without me filling in the form again and again, and I can keep using the app while it runs.

**How it should work**

1. **Start.** In the **Issue** tab, add a way to switch between **Single** (the current form) and **Bulk (CSV)**.
2. **Upload.** The user picks a CSV file. A **Download sample CSV** link gives a correct template. Drag and drop is a bonus.
3. **Check.** CertDesk reads the file and shows every row in a table with its status: *ready*, or the error for that row. A summary shows how many rows are ready and how many have errors. Nothing is issued yet.
4. **Approve.** The user clicks **Approve and issue N certificates**, or cancels. Only rows that are ready are issued; rows with errors are skipped.
5. **Background.** After approval, the work runs **in the background on the server**, and the approve request returns straight away. The user can move to other tabs (Certificates, Verify, Email setup) and the work keeps going. A progress indicator (for example "Bulk issue: 120 of 500") is visible from every tab, and the user is told when it finishes. After a page reload, the progress is still shown.
6. **Results.** When it is done, the user sees each row's result: *issued* (with the certificate ID) or *failed* (with the reason), and can download the results as a CSV. The new certificates appear in the Certificates list.
7. **Email.** If email setup is connected, every recipient is emailed their certificate from the configured address. If it is not, the certificates are issued without email, and the screen says so before the user approves (like the single Issue form does).

**CSV format**

| Column | Required | Rule |
|---|---|---|
| `recipient_name` | Yes | 2–100 characters |
| `recipient_email` | Yes | A valid email address |
| `course_name` | Yes | 2–150 characters |
| `issue_date` | Yes | `YYYY-MM-DD`, not in the future |

- The first row is the header. Columns can be in any order; extra columns are ignored.
- UTF-8 text. Spaces around values are trimmed. Empty lines are skipped.
- At most 500 rows and 1 MB per file. Bigger files are rejected with a clear message.

```
recipient_name,recipient_email,course_name,issue_date
Priya Nair,priya.nair@example.com,Flask Web Development,2026-03-25
Rohan Mehta,rohan.mehta@example.com,Flask Web Development,2026-03-25
```

**It is done when**

- Every row follows the same validation rules as a single certificate (`API_CONTRACT.md`, "Create a certificate").
- The duplicate rule applies **inside the file** and **against the database**: a recipient can't get two active certificates for the same course.
- The **server** checks the file. Never rely on checks done only in the browser.
- Nothing is issued before the user approves, and approving the same upload twice never issues certificates twice.
- One bad row never stops the other rows. A row that was fine at check time can still fail when it is issued (for example, someone issued the same certificate in the meantime). Report it as failed, with the reason.
- Only logged-in users can use bulk issue, and each user sees only their own uploads.
- Bulk jobs and their row results are stored in SQLite, so progress and results survive a page reload.

**Backend design: your choice**

Design the API yourself and add it to the **Bulk issue** section of `API_CONTRACT.md`, in the same style as the rest (method, path, request, responses, errors). One possible shape, which you can change:

| Endpoint | Purpose |
|---|---|
| `POST /api/bulk-issues` | Upload the CSV, check it, and return a preview: a job ID and every row with its status |
| `POST /api/bulk-issues/<job_id>/approve` | Start issuing in the background; returns `202 Accepted` |
| `GET /api/bulk-issues/<job_id>` | Progress and row results |
| `GET /api/bulk-issues/<job_id>/results.csv` | Download the results |

Build the screens in the existing frontend (`frontend/index.html`, `frontend/app.js`, `frontend/style.css`) and reuse the helpers in `frontend/common.js`. In `NOTES.md`, explain how your background processing works and what its limits are (for example, what happens if the server restarts in the middle of a job).

### Task 5: Tests

- All starter tests in `tests/` must pass.
- Add your own tests for every part: the certificate API (including error cases), each bug you fix, email setup (with SMTP mocked), and bulk issue (CSV checks, duplicates, partial success, the background job, approving twice).
- Focus on the cases most likely to break, not many copies of the happy path.
- Tip: make the background work easy to run synchronously in tests.

### Task 6: NOTES.md

Create `NOTES.md` with:

- Every bug: what it was, how you found it, how you fixed it, and what could go wrong if it stayed.
- Your design decisions: how you store the app password, how bulk issue runs in the background, and your bulk issue API.
- Assumptions you made where the spec was unclear.
- What you didn't finish, and what you would do next.

### Bonus (optional, only if you have time)

- Protect the write endpoints (create, revoke) with an API key sent in an `X-API-Key` header, read from an environment variable.
- A `Dockerfile`.
- A Postman / Bruno / HTTPie collection for the API.

---

## Rules

- **AI tools are allowed.** But you must understand every line you submit. A follow-up call (20–30 min) will ask you to explain your code and make a small change live.
- Work on your own. Don't share this assignment publicly.
- Write all backend code in Python with Flask.
- Work only in **your fork**. Make **small, clear commits**: we look at your commit history.

## How to submit

1. Push your work to **your fork**, never to this repository. Commit as you go.
2. Make sure `NOTES.md` is filled in.
3. Before the deadline, fill in the **submission form** linked in our email. It asks for your details, the link to your fork, and your project as a `.zip` file (without the `venv/` and `instance/` folders).
4. If your fork is private, give access to the reviewer we tell you about.

## How we will review

| Area | What we look for |
|---|---|
| Certificate API | Matches the contract: shapes, status codes, error format, login rules |
| Bugs | Found, fixed and explained clearly, with tests that prove the fixes |
| Email setup | Matches the contract; SMTP sign-in checked before saving; app password never returned and stored safely; SMTP mocked in tests |
| Bulk issue | Works end to end; correct row checks and duplicates; real background processing; progress survives tab changes and reloads; API documented in `API_CONTRACT.md` |
| Validation & errors | Bad input is handled cleanly; no crashes; no SQL injection |
| Tests | Useful tests for real edge cases, not just the happy path |
| Code quality | Readable, organised, no copy-paste repetition |
| Communication | Clear `NOTES.md` and commit messages |

Good luck! If something in the spec is unclear, make a reasonable choice and write it down in `NOTES.md`. That is part of the job too.
