# CertDesk – My Implementation Notes

## About the Project

I worked on the CertDesk application as part of the backend developer assignment. The application is used to issue and manage certificates. It also supports public certificate verification, email notifications, and issuing multiple certificates through a CSV file.

I first went through the existing code and understood how the frontend, backend, and database were connected. Then I started fixing the existing issues and implementing the remaining features.

Below are the changes I made and how I tested them.

## 1. Issues I Found and Fixed

### Date parsing issue – `app/helpers.py`

While checking the helper functions, I noticed that `parse_date()` was using the date format `%Y-%d-%m`. However, the application expects dates in `YYYY-MM-DD` format.

I changed it to `%Y-%m-%d`. This makes sure that issue dates are read in the correct year, month, and day order.

I also added a test to check whether dates are parsed correctly.

### Pagination issue – `app/helpers.py`

I found that the pagination function was calculating the offset using `page * limit`.

Because of this, the first page was skipping the initial records. For example, when the page number was 1 and the limit was 10, it started from offset 10 instead of 0.

I corrected the calculation to:

```python
offset = (page - 1) * limit
```

I tested the first-page calculation to make sure it starts from offset zero.

### Password storage – `app/auth.py`

While reviewing the login and signup code, I noticed that passwords were being stored using Base64 encoding.

Base64 is reversible, so it is not a safe way to store passwords. I replaced it with Werkzeug's `generate_password_hash()` and `check_password_hash()`.

Now, the application stores a password hash during signup and checks the entered password against that hash during login.

I also updated the demo account seeding logic to use the same password-hashing function.

I added a test to check that the original password is not stored directly in the database.

### CSV upload issue – `frontend/common.js`

When I tested bulk CSV uploading from the frontend, I found an issue with how the common API helper was setting request headers.

It was setting the JSON content type even when the request contained a CSV file using `FormData`.

I updated the helper to identify FormData requests and let the browser set the correct multipart content type. After this change, the CSV upload worked correctly.

### Bulk tab display issue – `frontend/index.html`

During manual testing, I noticed that the Bulk tab was opening, but its content was not visible.

The bulk section was not using the same `panel` class that the existing tab-switching code was expecting.

I corrected the class, and the bulk upload section started displaying properly.

## 2. Certificate APIs

I implemented the five certificate endpoints in `app/routes.py` based on the API contract.

The APIs support creating certificates, listing certificates, viewing an individual certificate, verifying a certificate publicly, and revoking an active certificate.

While implementing them, I also handled input validation, duplicate certificate checks, pagination, and search by recipient name.

I used parameterized SQL queries for database operations and kept the certificate management endpoints protected by login authentication. The public verification endpoint does not require login.

I also made sure that private recipient email information is not included in the public verification response.

## 3. Email Settings and Sending Emails

I implemented the email functionality in `app/email_settings.py`.

The application now supports:

- Viewing saved email settings.
- Adding or updating email settings.
- Sending a test email.
- Deleting saved email settings.
- Sending certificate details through email.

For Gmail, I used SMTP with the default host `smtp.gmail.com` and port `587`.

The SMTP connection uses SSL for port 465 and STARTTLS for other configured ports. I also added a 10-second connection timeout.

Before saving email settings, the application checks the SMTP login details. If the credentials are incorrect, it returns an appropriate error.

### How I handled email passwords

I did not want to store Gmail App Passwords directly in the database. So I used Fernet encryption from the `cryptography` package.

The encryption key is read from the `EMAIL_ENCRYPTION_KEY` environment variable. The encrypted password is stored in the database and decrypted only when the application needs to connect to SMTP.

The API responses do not return the saved password.

I also made sure that an email failure does not undo a certificate that has already been issued.

I tested the email functionality using mocked SMTP connections. I tested both SSL and STARTTLS connections, along with authentication and connection failures. I have not tested actual email delivery using a real Gmail account.

## 4. Bulk Certificate Upload

I implemented the bulk certificate feature so that users can upload a CSV file instead of entering certificate details one by one.

The CSV file should contain these columns:

- `recipient_name`
- `recipient_email`
- `course_name`
- `issue_date`

The columns can appear in any order. Extra columns are ignored, and empty rows are skipped.

I also added validation for the uploaded file:

- Maximum file size of 1 MB.
- Maximum of 500 data rows.
- Recipient name must contain 2–100 characters.
- Email address must be valid.
- Course name must contain 2–150 characters.
- Issue date must follow `YYYY-MM-DD` format.
- Future issue dates are not accepted.

The application checks for duplicate active certificates both within the uploaded file and in the existing database.

### How bulk processing works

After uploading a CSV, the user can see a preview of the records and which rows are ready or have validation errors.

Once the user approves the job, the application starts processing the valid rows in a background thread.

I used SQLite to save the bulk job information and individual row results. This helps the application show the job status and progress even after the page is refreshed.

If one row fails, the remaining valid rows can still be processed. The user can also download the processing results as a CSV file.

If email settings are available, the application attempts to send certificate emails after issuing the certificates.

I also added a synchronous processing option for tests so that bulk processing can be tested without relying on background thread timing.

## 5. Database and Other Implementation Details

I updated the database schema to support email settings and bulk processing.

Apart from the existing users and certificates tables, the application now has tables for email settings, bulk jobs, and individual bulk job rows.

I kept the email settings separate for each user. Bulk jobs are also associated with the user who created them.

For API responses, I used a consistent error structure so that the frontend can handle errors in a predictable way.

## 6. Testing I Performed

I added tests for the certificate APIs, authentication, email functionality, and bulk processing.

Some of the cases I checked include:

- Creating and retrieving certificates.
- Rejecting invalid certificate data.
- Verifying certificates without login.
- Revoking certificates.
- Preventing duplicate active certificates.
- Issuing a new certificate after revoking an earlier one.
- Checking pagination and recipient search.
- Preventing unauthenticated access to protected endpoints.
- Checking secure password storage.
- Saving and retrieving email settings.
- Checking that email passwords are not exposed.
- Testing SMTP SSL and STARTTLS connections.
- Handling SMTP authentication and connection failures.
- Uploading and validating CSV files.
- Approving bulk jobs and downloading their results.

For SMTP-related tests, I used mocks instead of sending actual emails.

I ran the complete test suite using:

```bash
pytest -v
```

The latest test run completed with **35 tests passing**.

### Manual testing

I also opened the application in the browser and tested the main workflows.

I logged in using the demo account, issued a certificate, and checked that it could be verified through the public verification page.

After that, I uploaded a CSV containing two valid records. Both records appeared in the preview, and after approving the job, both certificates were issued successfully.

I checked the completed job status and downloaded the results CSV.

I also opened the Email Setup page and checked that the Gmail defaults button correctly fills the SMTP host and port fields.

## 7. Things to Keep in Mind

A few things are worth mentioning about the current implementation:

- I used SQLite as the database for this assignment.
- Bulk processing currently uses Python background threads. For a larger production application, a dedicated task queue such as Celery or RQ would be a better option.
- Gmail email settings use App Passwords and require the `EMAIL_ENCRYPTION_KEY` to be configured.
- I tested SMTP behavior using mocks, but I have not connected a real Gmail account to verify actual email delivery.
- Certificate emails currently send certificate details, but I have not implemented a PDF certificate attachment.

## 8. Final Status

I have implemented the certificate APIs, email settings and SMTP integration, bulk CSV upload and processing, and the related frontend changes.

I also fixed the issues I found during development and added automated tests for the main workflows.

The latest test run completed successfully with 35 passing tests. I have also manually tested certificate issuance, public verification, bulk upload, approval, progress tracking, and results download through the browser.