import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.services import document_service
from app.services import auth_service

from datetime import datetime, timedelta, timezone

from app.models import User
from app.core.security import hash_verification_token
from app.core.config import settings

TEST_VERIFICATION_TOKENS = {}


@pytest.fixture
def client(tmp_path, monkeypatch):
    # An isolated, in-memory database for each test.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )
    app.state.TestingSessionLocal = TestingSessionLocal

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Keep test uploads outside the real storage directory.
    monkeypatch.setattr(
        document_service,
        "STORAGE_DIR",
        tmp_path / "test_uploads",
    )

    # Use a small limit to test oversized uploads cheaply.
    monkeypatch.setattr(document_service, "MAX_FILE_SIZE", 64)

    TEST_VERIFICATION_TOKENS.clear()

    def mock_send_verification_email(email, token):
        TEST_VERIFICATION_TOKENS[email] = token

    monkeypatch.setattr(
        auth_service,
        "send_verification_email",
        mock_send_verification_email,
    )

    assert (
        auth_service.send_verification_email
        is mock_send_verification_email
    )




    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    test_engine.dispose()


def register_and_login(client, email="student@example.com"):
    register_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )
    assert register_response.status_code == 201

    verification_token = TEST_VERIFICATION_TOKENS[email]

    verify_response = client.get(
        "/auth/verify-email",
        params={"token": verification_token},
    )
    assert verify_response.status_code == 200

    login_response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )
    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_documents_require_authentication(client):
    response = client.get("/documents/")
    assert response.status_code in (401, 403)


def test_register_login_and_get_current_user(client):
    headers = register_and_login(client)

    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "student@example.com"


def test_user_cannot_access_another_users_document(client):
    owner_headers = register_and_login(client, "owner@example.com")

    upload_response = client.post(
        "/documents/",
        headers=owner_headers,
        data={"title": "Test Notes"},
        files={
            "file": (
                "notes.pdf",
                b"%PDF-1.4\nTest PDF",
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    other_headers = register_and_login(client, "other@example.com")

    response = client.get(
        f"/documents/{document_id}",
        headers=other_headers,
    )

    assert response.status_code == 404


def test_user_cannot_update_another_users_document(client):
    owner_headers = register_and_login(client, "owner2@example.com")

    upload_response = client.post(
        "/documents/",
        headers=owner_headers,
        data={"title": "Private Notes"},
        files={
            "file": (
                "notes.pdf",
                b"%PDF-1.4\nTest PDF",
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    other_headers = register_and_login(client, "other2@example.com")

    response = client.patch(
    f"/documents/{document_id}",
    headers=other_headers,
    json={"title": "Hacked Title"},
)

    assert response.status_code == 404

def test_user_cannot_delete_another_users_document(client):
    owner_headers = register_and_login(client, "delete_owner@example.com")

    upload_response = client.post(
        "/documents/",
        headers=owner_headers,
        data={"title": "Private Notes"},
        files={
            "file": (
                "notes.pdf",
                b"%PDF-1.4\nTest PDF",
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    other_headers = register_and_login(client, "delete_other@example.com")

    response = client.delete(
        f"/documents/{document_id}",
        headers=other_headers,
    )

    assert response.status_code == 404

    # Confirm the original owner can still access the document.
    owner_response = client.get(
        f"/documents/{document_id}",
        headers=owner_headers,
    )
    assert owner_response.status_code == 200

def test_rejects_non_pdf_upload(client):
    headers = register_and_login(client)

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Not a PDF"},
        files={
            "file": (
                "notes.txt",
                b"plain text",
                "text/plain",
            )
        },
    )

    assert response.status_code == 415


def test_rejects_oversized_upload(client):
    headers = register_and_login(client)

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Too Large"},
        files={
            "file": (
                "large.pdf",
                b"%PDF-" + b"x" * 100,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413


def test_rejects_invalid_pdf_signature(client):
    headers = register_and_login(client)

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Fake PDF"},
        files={
            "file": (
                "fake.pdf",
                b"This is not a PDF",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 415


def test_oversized_upload_leaves_no_file_or_record(client):
    headers = register_and_login(client)

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Too Large"},
        files={
            "file": (
                "large.pdf",
                b"%PDF-" + b"x" * 100,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413

    documents_response = client.get(
        "/documents/",
        headers=headers,
    )
    assert documents_response.status_code == 200
    assert documents_response.json() == []

    upload_dir = document_service.STORAGE_DIR
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def test_invalid_pdf_leaves_no_file_or_record(client):
    headers = register_and_login(client)

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Fake PDF"},
        files={
            "file": (
                "fake.pdf",
                b"This is not a PDF",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 415

    documents_response = client.get(
        "/documents/",
        headers=headers,
    )
    assert documents_response.status_code == 200
    assert documents_response.json() == []

    upload_dir = document_service.STORAGE_DIR
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def create_test_document(client, headers, title="Study Notes"):
    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": title},
        files={
            "file": (
                "notes.pdf",
                b"%PDF-1.4\nTest PDF",
                "application/pdf",
            )
        },
    )
    assert response.status_code == 201
    return response.json()

def create_test_subject(client, headers, name="Python"):
    response = client.post(
        "/subjects/",
        params={"name": name},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def create_test_document_for_subject(
    client, headers, subject_id, title
):
    response = client.post(
        "/documents/",
        headers=headers,
        data={
            "title": title,
            "subject_id": str(subject_id),
        },
        files={
            "file": (
                "notes.pdf",
                b"%PDF-1.4\nTest PDF",
                "application/pdf",
            )
        },
    )
    assert response.status_code == 201
    return response.json()


def test_update_document_title(client):
    headers = register_and_login(client)
    document = create_test_document(client, headers)

    response = client.patch(
        f"/documents/{document['id']}",
        headers=headers,
        json={"title": "Updated Notes"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Notes"

    # Verify the change persists.
    get_response = client.get(
        f"/documents/{document['id']}",
        headers=headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Updated Notes"


def test_update_document_rejects_blank_title(client):
    headers = register_and_login(client)
    document = create_test_document(client, headers)

    response = client.patch(
        f"/documents/{document['id']}",
        headers=headers,
        json={"title": "   "},
    )

    assert response.status_code == 422


def test_cannot_update_another_users_document(client):
    owner_headers = register_and_login(client, "owner@example.com")
    document = create_test_document(client, owner_headers)

    other_headers = register_and_login(client, "other@example.com")

    response = client.patch(
        f"/documents/{document['id']}",
        headers=other_headers,
        json={"title": "Unauthorized Update"},
    )

    assert response.status_code == 404


def test_delete_document_removes_record_and_file(client):
    headers = register_and_login(client)
    document = create_test_document(client, headers)
    document_id = document["id"]

    # Capture the stored file before deleting the record.
    upload_dir = document_service.STORAGE_DIR
    stored_files = list(upload_dir.iterdir())
    assert len(stored_files) == 1
    stored_file = stored_files[0]
    assert stored_file.is_file()

    response = client.delete(
        f"/documents/{document_id}",
        headers=headers,
    )

    assert response.status_code == 204
    assert response.content == b""
    assert not stored_file.exists()

    # Verify the database record is gone.
    get_response = client.get(
        f"/documents/{document_id}",
        headers=headers,
    )
    assert get_response.status_code == 404

    list_response = client.get(
        "/documents/",
        headers=headers,
    )
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_repeated_delete_returns_404(client):
    headers = register_and_login(client)
    document = create_test_document(client, headers)
    url = f"/documents/{document['id']}"

    first_response = client.delete(url, headers=headers)
    assert first_response.status_code == 204

    second_response = client.delete(url, headers=headers)
    assert second_response.status_code == 404

def test_filter_documents_by_subject(client):
    headers = register_and_login(client)

    python_subject = create_test_subject(
        client, headers, "Python"
    )
    sql_subject = create_test_subject(
        client, headers, "SQL"
    )

    python_doc = create_test_document_for_subject(
        client, headers, python_subject["id"], "Python Handbook"
    )
    create_test_document_for_subject(
        client, headers, sql_subject["id"], "SQL Handbook"
    )

    response = client.get(
        "/documents/",
        headers=headers,
        params={"subject_id": python_subject["id"]},
    )

    assert response.status_code == 200

    documents = response.json()

    assert len(documents) == 1
    assert documents[0]["id"] == python_doc["id"]
    assert documents[0]["title"] == "Python Handbook"

def test_search_documents_by_title(client):
    headers = register_and_login(client)

    create_test_document(
        client, headers, "Python Handbook"
    )
    create_test_document(
        client, headers, "SQL Handbook"
    )

    response = client.get(
        "/documents/",
        headers=headers,
        params={"search": "python"},
    )

    assert response.status_code == 200

    documents = response.json()

    assert len(documents) == 1
    assert documents[0]["title"] == "Python Handbook"

def test_sort_documents_by_title_ascending(client):
    headers = register_and_login(client)

    create_test_document(client, headers, "SQL Handbook")
    create_test_document(client, headers, "Python Handbook")
    create_test_document(client, headers, "AI Handbook")

    response = client.get(
        "/documents/",
        headers=headers,
        params={
            "sort_by": "title",
            "order": "asc",
        },
    )

    assert response.status_code == 200

    titles = [doc["title"] for doc in response.json()]

    assert titles == [
        "AI Handbook",
        "Python Handbook",
        "SQL Handbook",
    ]

def test_sort_documents_by_title_descending(client):
    headers = register_and_login(client)

    create_test_document(client, headers, "SQL Handbook")
    create_test_document(client, headers, "Python Handbook")
    create_test_document(client, headers, "AI Handbook")

    response = client.get(
        "/documents/",
        headers=headers,
        params={
            "sort_by": "title",
            "order": "desc",
        },
    )

    assert response.status_code == 200

    titles = [doc["title"] for doc in response.json()]

    assert titles == [
        "SQL Handbook",
        "Python Handbook",
        "AI Handbook",
    ]

def test_document_pagination(client):
    headers = register_and_login(client)

    create_test_document(client, headers, "Alpha Notes")
    create_test_document(client, headers, "Beta Notes")
    create_test_document(client, headers, "Gamma Notes")

    first_response = client.get(
        "/documents/",
        headers=headers,
        params={
            "sort_by": "title",
            "order": "asc",
            "limit": 2,
            "offset": 0,
        },
    )

    second_response = client.get(
        "/documents/",
        headers=headers,
        params={
            "sort_by": "title",
            "order": "asc",
            "limit": 2,
            "offset": 2,
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_titles = [
        doc["title"] for doc in first_response.json()
    ]
    second_titles = [
        doc["title"] for doc in second_response.json()
    ]

    assert first_titles == ["Alpha Notes", "Beta Notes"]
    assert second_titles == ["Gamma Notes"]

def test_document_list_rejects_invalid_query_parameters(client):
    headers = register_and_login(client)

    invalid_queries = [
        {"sort_by": "password"},
        {"order": "sideways"},
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"subject_id": 0},
    ]

    for params in invalid_queries:
        response = client.get(
            "/documents/",
            headers=headers,
            params=params,
        )
        assert response.status_code == 422, (
            f"Expected 422 for {params}, got "
            f"{response.status_code}"
        )

def test_subject_filter_does_not_expose_another_users_documents(client):
    owner_headers = register_and_login(
        client, "owner@example.com"
    )
    other_headers = register_and_login(
        client, "other@example.com"
    )

    subject = create_test_subject(
        client, owner_headers, "Private Subject"
    )

    document = create_test_document_for_subject(
        client,
        owner_headers,
        subject["id"],
        "Private Notes",
    )

    response = client.get(
        "/documents/",
        headers=other_headers,
        params={"subject_id": subject["id"]},
    )

    assert response.status_code == 200
    assert all(
        doc["id"] != document["id"]
        for doc in response.json()
    )


def test_login_rejects_incorrect_password(client):
    register_response = client.post(
        "/auth/register",
        json={
            "email": "student@example.com",
            "password": "SecurePass123!",
        },
    )
    assert register_response.status_code in (200, 201)

    response = client.post(
        "/auth/login",
        json={
            "email": "student@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_unverified_user_cannot_login(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "unverified@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={
            "email": "unverified@example.com",
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 401
    assert "not verified" in login_response.json()["detail"].lower()


def test_email_verification_succeeds(client):
    email = "verify@example.com"

    register_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )

    assert register_response.status_code == 201

    token = TEST_VERIFICATION_TOKENS[email]

    verify_response = client.get(
        "/auth/verify-email",
        params={"token": token},
    )

    assert verify_response.status_code == 200
    assert "verified successfully" in (
        verify_response.json()["message"].lower()
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 200


def test_invalid_verification_token_is_rejected(client):
    response = client.get(
        "/auth/verify-email",
        params={"token": "invalid-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Verification link is invalid or expired."
    )


def test_expired_verification_token_is_rejected(client):
    email = "expired@example.com"

    register_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )
    assert register_response.status_code == 201

    token = TEST_VERIFICATION_TOKENS[email]

    TestingSessionLocal = client.app.state.TestingSessionLocal
    with TestingSessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None

        user.verification_token_expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        db.commit()

    response = client.get(
        "/auth/verify-email",
        params={"token": token},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Verification link is invalid or expired."
    )


def test_token_without_expiry_is_rejected(client):
    headers = register_and_login(client)

    token_without_expiry = jwt.encode(
        {"sub": "1"},
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    response = client.get(
        "/documents/",
        headers={
            "Authorization": f"Bearer {token_without_expiry}"
        },
    )

    assert response.status_code == 401

def test_expired_access_token_is_rejected(client):
    register_and_login(client)

    expired_token = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    response = client.get(
        "/documents/",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_malformed_access_token_is_rejected(client):
    response = client.get(
        "/documents/",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )

    assert response.status_code == 401
