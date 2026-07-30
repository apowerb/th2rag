from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from th2rag.models import User, UserLLMConfig
from th2rag.pagination import PageParams, PageResponse, paginate
from th2rag.utils.security import decrypt_key, encrypt_key, get_password_hash
from th2rag.users import exceptions, schemas
from th2rag.users.schemas import UserLLMConfigCreate


async def get_all_users(page_params: PageParams, db: AsyncSession) -> PageResponse[schemas.User]:
    stmt = select(User)
    return await paginate(db, stmt, page_params, schemas.User)


async def create_user(user_in: schemas.UserCreate, db: AsyncSession) -> schemas.User:
    stmt = select(User).where(User.email == user_in.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise exceptions.EmailAlreadyExists("Email already in use.")

    if user_in.password != None:
        hashed_password = get_password_hash(user_in.password)
    else:
        hashed_password = None

    user_in.password = hashed_password

    new_user = User(**user_in.model_dump())

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return schemas.User.model_validate(new_user)


async def get_user_by_id(user_id: int, db: AsyncSession) -> schemas.User:
    stmt = select(User).where(User.user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise exceptions.UserNotFoundException("User not found")

    return schemas.User.model_validate(user)


async def get_user_by_email(user_email: str, db: AsyncSession) -> schemas.User:
    stmt = select(User).where(User.email == user_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise exceptions.UserNotFoundException("User not found")

    return schemas.User.model_validate(user)


async def delete_user_by_id(user_id: int, db: AsyncSession) -> None:
    stmt = select(User).where(User.user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise exceptions.UserNotFoundException("User not found")

    await db.delete(user)
    await db.commit()


async def delete_user_by_email(user_email: str, db: AsyncSession) -> None:
    stmt = select(User).where(User.email == user_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise exceptions.UserNotFoundException("User not found")

    await db.delete(user)
    await db.commit()


async def create_or_update_llm_config(
    user_id: int, config: UserLLMConfigCreate, db: AsyncSession
) -> UserLLMConfig:
    """Create or update user LLM config"""
    stmt = select(UserLLMConfig).where(UserLLMConfig.user_id == user_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    # Encrypt API key
    encrypted_key = encrypt_key(config.api_key)

    if existing:
        # Update existing
        existing.provider = config.provider
        existing.model_name = config.model_name
        existing.api_key = encrypted_key
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        # Create new
        new_config = UserLLMConfig(
            user_id=user_id,
            provider=config.provider,
            model_name=config.model_name,
            api_key=encrypted_key,
        )
        db.add(new_config)
        await db.commit()
        await db.refresh(new_config)
        return new_config


async def get_llm_config(user_id: int, db: AsyncSession) -> UserLLMConfig | None:
    """Get user LLM config"""
    stmt = select(UserLLMConfig).where(UserLLMConfig.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_llm_config(user_id: int, db: AsyncSession) -> bool:
    """Delete user LLM config"""
    stmt = select(UserLLMConfig).where(UserLLMConfig.user_id == user_id)
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config:
        await db.delete(config)
        await db.commit()
        return True
    return False


def get_decrypted_api_key(config: UserLLMConfig) -> str:
    """Decrypt API key"""
    return decrypt_key(config.api_key)
