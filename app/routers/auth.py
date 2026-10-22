
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.security import create_access_token
from app.db.dependencies import get_db
from app.models import User
from app.schemas.auth import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import (
    authenticate_user,
    register_user,
    verify_user_email,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: UserRegister,
    db: Session = Depends(get_db),
):
    try:
        return register_user(
            db,
            email=str(payload.email).lower(),
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send verification email. Please try again.",
        ) from exc



@router.get("/verify-email")
def verify_email(
    token: str = Query(min_length=1),
    db: Session = Depends(get_db),
):
    verified = verify_user_email(db, token)

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link is invalid or expired.",
        )

    return {"message": "Email verified successfully. You can now log in."}


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    user = authenticate_user(
        db,
        email=str(payload.email).lower(),
        password=payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or email not verified.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user
