import pytest

from th2rag.users import exceptions, schemas, service


@pytest.mark.asyncio
async def test_create_user(async_db):
    user_in = schemas.UserCreate(first_name="John", last_name="Doe", email="johndoe@example.com")
    user = await service.create_user(user_in, async_db)

    assert user.first_name == "John"
    assert user.last_name == "Doe"
    assert user.email == "johndoe@example.com"

    with pytest.raises(exceptions.EmailAlreadyExists):
        await service.create_user(user_in, async_db)


@pytest.mark.asyncio
async def test_get_user_by_id(async_db):
    user_in = schemas.UserCreate(first_name="Alice", last_name="Wonder", email="alice@example.com")
    created_user = await service.create_user(user_in, async_db)

    fetched_user = await service.get_user_by_id(created_user.user_id, async_db)
    assert fetched_user.user_id == created_user.user_id
    assert fetched_user.email == created_user.email

    with pytest.raises(exceptions.UserNotFoundException):
        await service.get_user_by_id(9999, async_db)


@pytest.mark.asyncio
async def test_get_user_by_email(async_db):
    user_in = schemas.UserCreate(first_name="Bob", last_name="Builder", email="bob@example.com")
    created_user = await service.create_user(user_in, async_db)

    fetched_user = await service.get_user_by_email(created_user.email, async_db)
    assert fetched_user.user_id == created_user.user_id
    assert fetched_user.email == created_user.email

    with pytest.raises(exceptions.UserNotFoundException):
        await service.get_user_by_email("nonexistent@example.com", async_db)


@pytest.mark.asyncio
async def test_delete_user_by_id(async_db):
    user_in = schemas.UserCreate(first_name="Carol", last_name="Danvers", email="carol@example.com")
    created_user = await service.create_user(user_in, async_db)

    await service.delete_user_by_id(created_user.user_id, async_db)

    with pytest.raises(exceptions.UserNotFoundException):
        await service.get_user_by_id(created_user.user_id, async_db)


@pytest.mark.asyncio
async def test_delete_user_by_email(async_db):
    user_in = schemas.UserCreate(first_name="Dave", last_name="Grohl", email="dave@example.com")
    created_user = await service.create_user(user_in, async_db)

    await service.delete_user_by_email(created_user.email, async_db)

    with pytest.raises(exceptions.UserNotFoundException):
        await service.get_user_by_email(created_user.email, async_db)
