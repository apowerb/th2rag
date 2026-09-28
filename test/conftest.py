import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from th2rag.database import Base

Base.metadata.schema = None

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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
