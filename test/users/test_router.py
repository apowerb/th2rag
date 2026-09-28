import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from th2rag.database import get_db
from th2rag.dependencies import get_current_user
from th2rag.main import app
from th2rag.users import schemas


def _authenticate_as(user: dict) -> None:
    """The GET and DELETE routes require the owner (or an admin) to be signed in."""
    app.dependency_overrides[get_current_user] = lambda: schemas.User(**user)


@pytest_asyncio.fixture(autouse=True)
async def override_get_db(async_db):
    async def _get_db():
        yield async_db

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_user_router():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"first_name": "Test", "last_name": "User", "email": "test@example.com"}
        response = await client.post("/users/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "Test"
        assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_user_by_id_router():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"first_name": "Test", "last_name": "User", "email": "testid@example.com"}
        create_response = await client.post("/users/", json=payload)
        assert create_response.status_code == 201
        user = create_response.json()
        _authenticate_as(user)
        user_id = user["user_id"]
        response = await client.get(f"/users/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user_id


@pytest.mark.asyncio
async def test_get_user_by_email_router():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"first_name": "Test", "last_name": "User", "email": "testemail@example.com"}
        create_response = await client.post("/users/", json=payload)
        assert create_response.status_code == 201
        user = create_response.json()
        _authenticate_as(user)
        email = user["email"]
        response = await client.get(f"/users/email/{email}")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email


@pytest.mark.asyncio
async def test_delete_user_by_id_router():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"first_name": "Test", "last_name": "User", "email": "deleteid@example.com"}
        create_response = await client.post("/users/", json=payload)
        assert create_response.status_code == 201
        user = create_response.json()
        _authenticate_as(user)
        user_id = user["user_id"]
        del_response = await client.delete(f"/users/{user_id}")
        assert del_response.status_code == 204
        get_response = await client.get(f"/users/{user_id}")
        assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_by_email_router():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"first_name": "Test", "last_name": "User", "email": "deleteemail@example.com"}
        create_response = await client.post("/users/", json=payload)
        assert create_response.status_code == 201
        user = create_response.json()
        _authenticate_as(user)
        email = user["email"]
        del_response = await client.delete(f"/users/email/{email}")
        assert del_response.status_code == 204
        get_response = await client.get(f"/users/email/{email}")
        assert get_response.status_code == 404


def _other_user(role: str) -> dict:
    """A signed-in user distinct from the one each test creates."""
    return {
        "user_id": 9999,
        "email": "someone-else@example.com",
        "first_name": "Other",
        "last_name": "User",
        "role": role,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }


@pytest.mark.asyncio
async def test_admin_can_read_another_user():
    # get_current_user returns the stored role, "ADMIN" in uppercase.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"first_name": "Test", "last_name": "User", "email": "readbyadmin@example.com"}
        create_response = await client.post("/users/", json=payload)
        assert create_response.status_code == 201
        user = create_response.json()
        _authenticate_as(_other_user("ADMIN"))
        by_id = await client.get(f"/users/{user['user_id']}")
        assert by_id.status_code == 200, by_id.text
        by_email = await client.get(f"/users/email/{user['email']}")
        assert by_email.status_code == 200, by_email.text


@pytest.mark.asyncio
async def test_non_owner_cannot_read_another_user():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"first_name": "Test", "last_name": "User", "email": "notmine@example.com"}
        create_response = await client.post("/users/", json=payload)
        assert create_response.status_code == 201
        user = create_response.json()
        _authenticate_as(_other_user("USER"))
        by_id = await client.get(f"/users/{user['user_id']}")
        assert by_id.status_code == 403, by_id.text
        by_email = await client.get(f"/users/email/{user['email']}")
        assert by_email.status_code == 403, by_email.text
