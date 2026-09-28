import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from th2rag.database import get_db
from th2rag.dependencies import get_current_user
from th2rag.main import app


@pytest_asyncio.fixture(autouse=True)
async def override_get_db(async_db, current_user):
    async def _get_db():
        yield async_db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_conversation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"title": "Test Conversation", "knowledge_id": 1}
        response = await client.post("/conversations", json=payload)
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["title"] == payload["title"]
        assert data["knowledge_id"] == payload["knowledge_id"]
        assert "conversation_id" in data


@pytest.mark.asyncio
async def test_get_conversation_by_id():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"title": "Test Get Conversation", "knowledge_id": 1}
        create_response = await client.post("/conversations", json=payload)
        assert create_response.status_code == 201, create_response.text
        created_data = create_response.json()
        conversation_id = created_data["conversation_id"]

        get_response = await client.get(f"/conversations/{conversation_id}")
        assert get_response.status_code == 200, get_response.text
        data = get_response.json()
        assert data["conversation_id"] == conversation_id
        assert data["title"] == payload["title"]


@pytest.mark.asyncio
async def test_get_all_conversations():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"title": "Test All Conversations", "knowledge_id": 1}
        create_response = await client.post("/conversations", json=payload)
        assert create_response.status_code == 201, create_response.text

        response = await client.get("/conversations")
        assert response.status_code == 200, response.text
        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0


@pytest.mark.asyncio
async def test_delete_conversation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"title": "Test Delete Conversation", "knowledge_id": 1}
        create_response = await client.post("/conversations", json=payload)
        assert create_response.status_code == 201, create_response.text
        created_data = create_response.json()
        conversation_id = created_data["conversation_id"]

        delete_response = await client.delete(f"/conversations/{conversation_id}")
        assert delete_response.status_code == 204, delete_response.text

        get_response = await client.get(f"/conversations/{conversation_id}")
        assert get_response.status_code == 404, get_response.text
