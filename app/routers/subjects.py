
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.dependencies import get_db
from app.models import User
from app.services.subject_service import create_subject, list_subjects

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_subject_endpoint(
    name: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    name = name.strip()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Subject name cannot be empty",
        )

    return create_subject(
        db=db,
        name=name,
        current_user=current_user,
    )


@router.get("/")
def list_subjects_endpoint(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return list_subjects(
        db=db,
        current_user=current_user,
    )
