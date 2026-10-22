from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Document, Subject, User


def create_subject(db: Session, name: str, current_user: User) -> Subject:
    subject = Subject(
        name=name,
        owner_id=current_user.id,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)

    return subject


def list_subjects(db: Session, current_user: User) -> list[Subject]:
    statement = select(Subject).where(
        Subject.owner_id == current_user.id
    )
    return list(db.scalars(statement).all())


def delete_subject(
    db: Session,
    subject_id: int,
    current_user: User,
) -> None:
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

    try:
        # Keep documents, but remove their subject assignment.
        db.execute(
            update(Document)
            .where(
                Document.subject_id == subject_id,
                Document.owner_id == current_user.id,
            )
            .values(subject_id=None)
        )

        db.delete(subject)
        db.commit()
    except Exception:
        db.rollback()
        raise
