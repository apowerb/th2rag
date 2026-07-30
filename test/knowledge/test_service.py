import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.knowledge import exceptions, service
from th2rag.models import Status
from th2rag.pagination import PageParams


@pytest.fixture(autouse=True)
def override_upload(monkeypatch):
    monkeypatch.setattr(
        service,
        "upload_file_to_s3",
        lambda file_bytes, filename: "https://dummy.s3.amazonaws.com/" + filename,
    )


@pytest.mark.asyncio
async def test_get_all_knowledges_empty(async_db: AsyncSession):
    page_params = PageParams(page=1, size=10)
    result = await service.get_all_knowledges(page_params, async_db)
    assert hasattr(result, "results")
    assert len(result.results) == 0


@pytest.mark.asyncio
async def test_create_knowledge(async_db: AsyncSession):
    name = "Test Knowledge"
    description = "Test description"
    filename = "test.txt"
    file_bytes = b"dummy content"
    created = await service.create_knowledge(name, description, filename, file_bytes, async_db)
    assert created.name == name
    assert created.description == description
    assert created.knowledge_path == "https://dummy.s3.amazonaws.com/" + filename
    assert created.status == Status.PENDING


@pytest.mark.asyncio
async def test_get_knowledge_by_id(async_db: AsyncSession):
    name = "Test Knowledge"
    description = "Test description"
    filename = "test.txt"
    file_bytes = b"dummy content"
    created = await service.create_knowledge(name, description, filename, file_bytes, async_db)
    fetched = await service.get_knowledge_by_id(created.knowledge_id, async_db)
    assert fetched.knowledge_id == created.knowledge_id


@pytest.mark.asyncio
async def test_get_knowledge_by_id_not_found(async_db: AsyncSession):
    with pytest.raises(exceptions.KnowledgeNotFoundException):
        await service.get_knowledge_by_id(9999, async_db)


@pytest.mark.asyncio
async def test_update_knowledge_status(async_db: AsyncSession):
    name = "Test Knowledge"
    description = "Test description"
    filename = "test.txt"
    file_bytes = b"dummy content"
    created = await service.create_knowledge(name, description, filename, file_bytes, async_db)
    await service.update_knowledge_status(created.knowledge_id, Status.COMPLETED, async_db)
    updated = await service.get_knowledge_by_id(created.knowledge_id, async_db)
    assert updated.status == Status.COMPLETED


@pytest.mark.asyncio
async def test_update_knowledge_status_not_found(async_db: AsyncSession):
    with pytest.raises(exceptions.KnowledgeNotFoundException):
        await service.update_knowledge_status(9999, Status.COMPLETED, async_db)


@pytest.mark.asyncio
async def test_delete_knowledge(async_db: AsyncSession):
    name = "Test Knowledge"
    description = "Test description"
    filename = "test.txt"
    file_bytes = b"dummy content"
    created = await service.create_knowledge(name, description, filename, file_bytes, async_db)
    knowledge_id = created.knowledge_id
    await service.delete_knowledge(knowledge_id, async_db)
    with pytest.raises(exceptions.KnowledgeNotFoundException):
        await service.get_knowledge_by_id(knowledge_id, async_db)


@pytest.mark.asyncio
async def test_delete_knowledge_not_found(async_db: AsyncSession):
    with pytest.raises(exceptions.KnowledgeNotFoundException):
        await service.delete_knowledge(9999, async_db)
