
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, Subject, User

STORAGE_DIR = Path("storage/documents").resolve()
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MiB
CHUNK_SIZE = 1024 * 1024


async def create_document(
    db: Session,
    current_user: User,
    title: str,
    file: UploadFile,
    subject_id: int | None = None,
) -> Document:
    title = title.strip()

    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title cannot be empty",
        )

    # A subject must belong to the authenticated user.
    if subject_id is not None:
        subject = db.scalar(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.owner_id == current_user.id,
            )
        )
        if subject is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found",
            )

    # MIME type is only a preliminary check; it is not proof
    # that the uploaded content is a safe PDF.
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF uploads are accepted",
        )

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}.pdf"
    destination = STORAGE_DIR / filename
    temporary = STORAGE_DIR / f".{uuid4().hex}.tmp"

    total_size = 0
    header = b""

    try:
        with temporary.open("xb") as output:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break

                if not header:
                    header = chunk[:5]

                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="PDF must be 50 MiB or smaller",
                    )

                output.write(chunk)

        if total_size == 0 or header != b"%PDF-":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File is empty or does not have a PDF signature",
            )

        # Atomic rename within the same filesystem.
        temporary.replace(destination)

        document = Document(
            title=title,
            file_path=str(destination),
            file_size=total_size,
            owner_id=current_user.id,
            subject_id=subject_id,
        )

        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    except Exception:
        db.rollback()
        temporary.unlink(missing_ok=True)

        # Best-effort compensation if a later operation fails.
        # Production deployments should also run orphan-file cleanup.
        if destination.exists():
            destination.unlink(missing_ok=True)

        raise

    finally:
        await file.close()


def update_document(
    db: Session,
    current_user: User,
    document_id: int,
    updates: dict,
) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == current_user.id,
        )
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if "title" in updates:
        title = updates["title"].strip()

        if not title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Title cannot be empty",
            )

        document.title = title

    if "subject_id" in updates:
        subject_id = updates["subject_id"]

        if subject_id is not None:
            subject = db.scalar(
                select(Subject).where(
                    Subject.id == subject_id,
                    Subject.owner_id == current_user.id,
                )
            )

            if subject is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Subject not found",
                )

        document.subject_id = subject_id

    db.commit()
    db.refresh(document)
    return document


def delete_document(
    db: Session,
    current_user: User,
    document_id: int,
) -> None:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == current_user.id,
        )
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    file_path = Path(document.file_path).resolve()

    # Ensure the file is inside StudyVault's document storage.
    if file_path.parent != STORAGE_DIR:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid document storage path",
        )

    # Commit the database deletion first.
    try:
        db.delete(document)
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Delete the physical file after the database commit.
    # If cleanup fails, the database record is already deleted;
    # log the failure and clean up the orphan file operationally.
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        import logging

        logging.getLogger(__name__).exception(
            "Failed to remove document file: %s", file_path
        )

