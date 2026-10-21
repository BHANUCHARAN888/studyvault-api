from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.dependencies import get_db
from app.models import Document, User
from app.schemas.document import DocumentResponse, DocumentUpdate
from app.services.document_service import (
    create_document, 
    update_document,
    delete_document,
    )

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("/", response_model=list[DocumentResponse])
def list_documents(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    statement = select(Document).where(
        Document.owner_id == current_user.id
    )
    return db.scalars(statement).all()


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    statement = select(Document).where(
        Document.id == document_id,
        Document.owner_id == current_user.id,
    )

    document = db.scalar(statement)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    title: Annotated[str, Form(min_length=1, max_length=255)],
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    subject_id: Annotated[int | None, Form()] = None,
):
    return await create_document(
        db=db,
        current_user=current_user,
        title=title,
        file=file,
        subject_id=subject_id,
    )


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
)
def update_document_endpoint(
    document_id: int,
    updates: DocumentUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return update_document(
        db=db,
        current_user=current_user,
        document_id=document_id,
        updates=updates.model_dump(exclude_unset=True),
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document_endpoint(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    delete_document(
        db=db,
        current_user=current_user,
        document_id=document_id,
    )
