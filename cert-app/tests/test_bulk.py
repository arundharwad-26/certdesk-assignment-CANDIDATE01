
import io


def test_upload_valid_csv_creates_preview(client):
    csv_content = (
        "recipient_name,recipient_email,course_name,issue_date\n"
        "John Doe,john.bulk@example.com,Python Programming,2026-11-17\n"
    )

    response = client.post(
        "/api/bulk-issues",
        data={
            "file": (
                io.BytesIO(csv_content.encode("utf-8")),
                "certificates.csv",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201

    data = response.get_json()["data"]

    assert data["filename"] == "certificates.csv"
    assert data["status"] == "preview"
    assert data["total_rows"] == 1
    assert data["ready_rows"] == 1
    assert data["error_rows"] == 0

    assert data["rows"][0]["status"] == "ready"
    assert data["rows"][0]["data"]["recipient_email"] == (
        "john.bulk@example.com"
    )

def test_bulk_upload_approve_and_download_results(client):
    client.application.config["BULK_RUN_SYNCHRONOUSLY"] = True

    csv_content = (
        "recipient_name,recipient_email,course_name,issue_date\n"
        "Jane Doe,jane.bulk@example.com,Data Science,2026-11-17\n"
    )

    # 1. Upload CSV.
    upload_response = client.post(
        "/api/bulk-issues",
        data={
            "file": (
                io.BytesIO(csv_content.encode("utf-8")),
                "bulk.csv",
            )
        },
        content_type="multipart/form-data",
    )

    assert upload_response.status_code == 201

    job_id = upload_response.get_json()["data"]["job_id"]

    # 2. Approve the job.
    approve_response = client.post(
        f"/api/bulk-issues/{job_id}/approve"
    )

    assert approve_response.status_code == 202

    # 3. Check processing status.
    status_response = client.get(
        f"/api/bulk-issues/{job_id}"
    )

    assert status_response.status_code == 200

    job = status_response.get_json()["data"]

    assert job["status"] == "completed"
    assert job["processed_rows"] == 1
    assert job["rows"][0]["status"] == "issued"
    assert job["rows"][0]["cert_id"].startswith("CERT-")

    # 4. Confirm a second approval is rejected.
    duplicate_approval = client.post(
        f"/api/bulk-issues/{job_id}/approve"
    )

    assert duplicate_approval.status_code == 409

    # 5. Download the results CSV.
    download_response = client.get(
        f"/api/bulk-issues/{job_id}/results.csv"
    )

    assert download_response.status_code == 200
    assert "jane.bulk@example.com" in download_response.get_data(as_text=True)
