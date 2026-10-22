
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_verification_token,
    hash_password,
    hash_verification_token,
    verification_token_expiry,
    verify_password,
)
from app.models import User
from app.services.email_service import send_verification_email


def register_user(db: Session, email: str, password: str) -> User:
    email = email.lower().strip()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise ValueError("Email is already registered")

    raw_token = create_verification_token()

    user = User(
        email=email,
        password_hash=hash_password(password),
        is_verified=False,
        verification_token_hash=hash_verification_token(raw_token),
        verification_token_expires_at=verification_token_expiry(),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    try:
        send_verification_email(email, raw_token)
    except Exception:
        # Remove the newly created account if the verification email
        # cannot be sent, so registration can be retried cleanly.
        db.delete(user)
        db.commit()
        raise

    return user


def verify_user_email(db: Session, token: str) -> bool:
    token_hash = hash_verification_token(token)

    user = db.scalar(
        select(User).where(
            User.verification_token_hash == token_hash
        )
    )

    if user is None:
        return False

    expires_at = user.verification_token_expires_at
    if expires_at is None:
        return False

    # PostgreSQL returns timezone-aware timestamps for this column.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= datetime.now(timezone.utc):
        return False

    user.is_verified = True
    user.verification_token_hash = None
    user.verification_token_expires_at = None

    db.commit()
    db.refresh(user)
    return True


def authenticate_user(
    db: Session, email: str, password: str
) -> User | None:
    user = db.scalar(
        select(User).where(User.email == email.lower().strip())
    )

    if user is None:
        return None

    if not verify_password(password, user.password_hash):
        return None

    if not user.is_verified:
        return None

    return user
