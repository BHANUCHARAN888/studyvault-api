
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Subject, User


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
