import pytest_asyncio
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from th2rag.database import Base

Base.metadata.schema = None

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(type_, compiler, **kw):
    # The models declare PostgreSQL JSONB; SQLite has no such type, so
    # create_all failed before any async_db test ran. SQLite's JSON type
    # already handles the values: only the DDL needs the name.
    return "JSON"


@pytest_asyncio.fixture
async def async_db():
    # Each aiosqlite connection runs on a non-daemon thread that only stops when
    # the connection is closed: an engine left undisposed keeps the interpreter
    # from exiting after the run. The finally also covers a failing setup.
    engine = create_async_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
    session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            yield session

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_user(async_db):
    """A stored user: conversations and knowledge require an owner."""
    # Imported here: the models must be declared after the schema reset above.
    from th2rag.models import User

    user = User(first_name="Test", last_name="Owner", email="owner@example.com")
    async_db.add(user)
    await async_db.commit()
    await async_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def current_user(db_user):
    """db_user as the authenticated user the services and routes receive."""
    from th2rag.users import schemas as user_schemas

    return user_schemas.User(
        user_id=db_user.user_id,
        email=db_user.email,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        role=db_user.role.value,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
    )
