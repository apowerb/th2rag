import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from th2rag.database import get_db
from th2rag.main import app


@pytest_asyncio.fixture(autouse=True)
async def bypass_jwt_middleware():
    original_middlewares = app.user_middleware.copy()
    app.user_middleware = []
    app.middleware_stack = app.build_middleware_stack()
    yield
    app.user_middleware = original_middlewares
    app.middleware_stack = app.build_middleware_stack()


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
        email = user["email"]
        del_response = await client.delete(f"/users/email/{email}")
        assert del_response.status_code == 204
        get_response = await client.get(f"/users/email/{email}")
        assert get_response.status_code == 404
