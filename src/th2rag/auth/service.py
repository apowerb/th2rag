from datetime import timedelta

import jwt
from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.auth import exceptions, schemas
from th2rag.config import settings
from th2rag.models import User
from th2rag.users.schemas import User as UserSchema
from th2rag.utils.security import create_access_token, verify_password


async def get_current_user_from_token(token: str, db: AsyncSession) -> UserSchema:
    """
    Validate a Bearer JWT token and return the corresponding user.
    Reuses the same JWT settings as login/refresh.
    """
    try:
        payload = jwt.decode(token, settings.encrypt_key, algorithms=[settings.algorithm])
        if payload.get("type") != "access":
            raise exceptions.InvalidCredentials("Invalid token type")
    except Exception:
        raise exceptions.InvalidCredentials("Invalid or expired token") from None

    user_email = payload.get("sub")
    if not user_email:
        raise exceptions.InvalidCredentials("Invalid token payload")

    stmt = select(User).where(User.email == user_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise exceptions.InvalidCredentials("User not found")

    return UserSchema(
        user_id=user.user_id,
        email=user.email,
        role=user.role.value,
        first_name=user.first_name,
        last_name=user.last_name,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def login(request: schemas.LoginRequest, response: Response, db: AsyncSession):
    stmt = select(User).where(User.email == request.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise exceptions.InvalidCredentials("Invalid email or password")

    if user.password is None:
        raise exceptions.InvalidCredentials("Invalid email or password")

    if verify_password(request.password, user.password) is False:
        raise exceptions.InvalidCredentials("Invalid email or password")

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.name, "type": "access"},
        expires_delta=access_token_expires,
    )

    refresh_token_expires = timedelta(days=30)
    refresh_token = create_access_token(
        data={"sub": user.email, "role": "USER", "type": "refresh"},
        expires_delta=refresh_token_expires,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=30 * 24 * 60 * 60,
        secure=(settings.working_mode != "development"),
        samesite="lax",
        path="/",
    )

    return schemas.Token(access_token=access_token, token_type="bearer")


async def refresh(request: Request, db: AsyncSession):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise exceptions.InvalidCredentials("Missing refresh token")

    try:
        payload = jwt.decode(refresh_token, settings.encrypt_key, algorithms=[settings.algorithm])
        if payload.get("type") != "refresh":
            raise exceptions.InvalidCredentials("Invalid token type")
    except Exception:
        raise exceptions.InvalidCredentials("Invalid or expired token") from None

    user_email = payload.get("sub")
    if not user_email:
        raise exceptions.InvalidCredentials("Invalid token")

    stmt = select(User).where(User.email == user_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise exceptions.InvalidCredentials("User not found")

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email, "role": "USER", "type": "access"},
        expires_delta=access_token_expires,
    )

    return schemas.Token(access_token=access_token, token_type="bearer")
