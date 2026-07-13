from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from backend.app.core.time import shanghai_now
from backend.app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
    }


def _token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "user": _serialize_user(user),
    }


def _lock_user_registration(db: Session) -> Optional[Connection]:
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    elif dialect == "postgresql":
        db.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
    elif dialect in {"mysql", "mariadb"}:
        lock_connection = db.get_bind().connect()
        try:
            acquired = lock_connection.scalar(text("SELECT GET_LOCK('xhs_user_registration', 10)"))
        except Exception:
            lock_connection.invalidate()
            lock_connection.close()
            raise
        if acquired != 1:
            lock_connection.close()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User registration is busy; retry shortly",
            )
        return lock_connection
    else:
        db.execute(select(User.id).order_by(User.id).limit(1).with_for_update())
    return None


def _unlock_user_registration(lock_connection: Optional[Connection]) -> None:
    if lock_connection is None:
        return
    released = False
    try:
        released = lock_connection.scalar(text("SELECT RELEASE_LOCK('xhs_user_registration')")) == 1
    finally:
        if not released:
            lock_connection.invalidate()
        lock_connection.close()


@router.post("/register")
def register(credentials: AuthCredentials, db: Session = Depends(get_db)):
    username = credentials.username.strip()
    lock_connection = _lock_user_registration(db)
    try:
        existing_user = db.scalar(select(User).where(User.username == username))
        if existing_user is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

        is_first_user = db.scalar(select(User.id).limit(1)) is None
        user = User(
            username=username,
            password_hash=hash_password(credentials.password),
            is_admin=is_first_user,
            is_active=True,
            last_login_at=shanghai_now(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return _token_response(user)
    finally:
        _unlock_user_registration(lock_connection)


@router.post("/login")
def login(credentials: AuthCredentials, db: Session = Depends(get_db)):
    username = credentials.username.strip()
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
    user.last_login_at = shanghai_now()
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/refresh")
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    decoded = decode_token(payload.refresh_token)
    if decoded.get("token_type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.get(User, decoded["user_id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.post("/logout")
def logout():
    return {"status": "ok"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _serialize_user(current_user)
