import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.services import document_service


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
    assert register_response.status_code in (200, 201)

    login_response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


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

