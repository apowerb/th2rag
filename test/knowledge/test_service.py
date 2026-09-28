import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.knowledge import exceptions, service
from th2rag.models import Status
from th2rag.pagination import PageParams

NAME = "Test Knowledge"
DESCRIPTION = "Test description"
FILENAME = "test.txt"


class _FakeLanceDBStorage:
    def delete_chunks(self, doc_id: int) -> None:
        pass


@pytest.fixture(autouse=True)
def isolate_storage(monkeypatch):
    monkeypatch.setattr(
        service,
        "upload_file_to_s3",
        lambda file_bytes, filename, knowledge_id: "https://dummy.s3.amazonaws.com/" + filename,
    )
    monkeypatch.setattr(service, "delete_file_from_s3", lambda path: None)
    monkeypatch.setattr(service, "LanceDBStorage", _FakeLanceDBStorage)


async def _create_knowledge(db: AsyncSession, user_id: int):
    return await service.create_knowledge_with_multiple_files(
        name=NAME,
        description=DESCRIPTION,
        prompt="Test prompt",
        files_data=[{"filename": FILENAME, "bytes": b"dummy content"}],
        user_id=user_id,
        db=db,
    )


@pytest.mark.asyncio
async def test_get_all_knowledges_empty(async_db: AsyncSession, current_user):
    page_params = PageParams(page=1, size=10)
    result = await service.get_all_knowledges(page_params, current_user, async_db)
    assert hasattr(result, "results")
    assert len(result.results) == 0


@pytest.mark.asyncio
async def test_create_knowledge(async_db: AsyncSession, db_user):
    created = await _create_knowledge(async_db, db_user.user_id)
    assert created.name == NAME
    assert created.description == DESCRIPTION
    assert created.knowledge_path == "https://dummy.s3.amazonaws.com/" + FILENAME
    assert created.status == Status.PENDING


@pytest.mark.asyncio
async def test_get_knowledge_by_id(async_db: AsyncSession, db_user):
    created = await _create_knowledge(async_db, db_user.user_id)
    fetched = await service.get_knowledge_by_id(created.knowledge_id, async_db)
    assert fetched.knowledge_id == created.knowledge_id


@pytest.mark.asyncio
async def test_get_knowledge_by_id_not_found(async_db: AsyncSession):
    with pytest.raises(exceptions.KnowledgeNotFoundException):
        await service.get_knowledge_by_id(9999, async_db)


@pytest.mark.asyncio
async def test_update_knowledge_status(async_db: AsyncSession, db_user):
    created = await _create_knowledge(async_db, db_user.user_id)
    await service.update_knowledge_status(created.knowledge_id, Status.COMPLETED, async_db)
    updated = await service.get_knowledge_by_id(created.knowledge_id, async_db)
    assert updated.status == Status.COMPLETED


@pytest.mark.asyncio
async def test_update_knowledge_status_not_found(async_db: AsyncSession):
    with pytest.raises(exceptions.KnowledgeNotFoundException):
        await service.update_knowledge_status(9999, Status.COMPLETED, async_db)


@pytest.mark.asyncio
async def test_delete_knowledge(async_db: AsyncSession, db_user):
    created = await _create_knowledge(async_db, db_user.user_id)
    knowledge_id = created.knowledge_id
    await service.delete_knowledge(knowledge_id, async_db)
    with pytest.raises(exceptions.KnowledgeNotFoundException):
        await service.get_knowledge_by_id(knowledge_id, async_db)


@pytest.mark.asyncio
async def test_delete_knowledge_not_found(async_db: AsyncSession):
    with pytest.raises(exceptions.KnowledgeNotFoundException):
        await service.delete_knowledge(9999, async_db)
