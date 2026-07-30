from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.config import settings
from th2rag.database import get_db
from th2rag.models import User as UserModel
from th2rag.models import UserLLMConfig
from th2rag.rag.services.rag_service import RAGService
from th2rag.rag.services.rag_service_builder import RAGServiceBuilder
from th2rag.users import schemas as user_schemas

# 🔓 Make authentication optional
security = HTTPBearer(auto_error=False)
DBSessionDep = Annotated[AsyncSession, Depends(get_db)]

# 🔥 HARDCODED BYPASS - SET TO False FOR PRODUCTION
BYPASS_AUTH = False


# ==========================================
# 1. DEFINE USER AUTH FIRST (So others can use it)
# ==========================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> user_schemas.User:

    # 🔓 AUTH BYPASS - NO DATABASE ACCESS
    if BYPASS_AUTH:
        print("AUTH BYPASS ACTIVE - Using fake user")

        # Return fake user with ALL required fields
        return user_schemas.User(
            user_id=1,
            email="test@example.com",
            role="USER",
            first_name="Test",
            last_name="User",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.encrypt_key,
            algorithms=[settings.algorithm]
        )

        # F14 fix: reject refresh tokens used as access tokens
        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    result = await db.execute(
        select(UserModel).where(UserModel.email == email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_schemas.User(
        user_id=user.user_id,
        email=user.email,
        role=user.role.value,
        first_name=user.first_name,
        last_name=user.last_name,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


# ==========================================
# 2. THEN DEFINE RAG SERVICE (Which uses the user)
# ==========================================

async def get_rag_service(
    current_user: user_schemas.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RAGService:
    
    # 1. Check if this user has a custom LLM Config in the database
    stmt = select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.user_id)
    result = await db.execute(stmt)
    user_config = result.scalar_one_or_none()

    # 2. Pass that config (or None) to the Builder
    builder = RAGServiceBuilder()
    return builder.build(user_config=user_config)


async def get_admin_user(
    current_user: user_schemas.User = Depends(get_current_user),
) -> user_schemas.User:

    if BYPASS_AUTH:
        print("⚠️  ADMIN BYPASS ACTIVE")
        current_user.role = "ADMIN"
        return current_user

    if getattr(current_user, "role", None) != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Not enough permissions")
    return current_user
