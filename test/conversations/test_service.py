import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.conversations import exceptions, schemas, service
from th2rag.models import Knowledge
from th2rag.pagination import PageParams


@pytest.mark.asyncio
async def test_get_all_conversations_empty(async_db: AsyncSession, current_user):
    page_params = PageParams(page=1, size=10)
    page_response = await service.get_all_conversations(page_params, current_user, async_db)
    assert hasattr(page_response, "results")
    assert len(page_response.results) == 0


@pytest.mark.asyncio
async def test_create_conversation(async_db: AsyncSession, db_user):
    knowledge = Knowledge(
        name="Test Knowledge", knowledge_path="/path/to/knowledge", user_id=db_user.user_id
    )
    async_db.add(knowledge)
    await async_db.commit()
    await async_db.refresh(knowledge)
    conv_in = schemas.ConversationCreate(
        title="Test Conversation", knowledge_id=knowledge.knowledge_id
    )
    created_conv = await service.create_conversation(conv_in, db_user.user_id, async_db)
    assert created_conv.title == "Test Conversation"
    assert created_conv.knowledge_id == knowledge.knowledge_id


@pytest.mark.asyncio
async def test_get_conversation_by_id(async_db: AsyncSession, db_user):
    knowledge = Knowledge(
        name="Test Knowledge", knowledge_path="/path/to/knowledge", user_id=db_user.user_id
    )
    async_db.add(knowledge)
    await async_db.commit()
    await async_db.refresh(knowledge)
    conv_in = schemas.ConversationCreate(
        title="Test Conversation", knowledge_id=knowledge.knowledge_id
    )
    created_conv = await service.create_conversation(conv_in, db_user.user_id, async_db)
    fetched_conv = await service.get_conversation_by_id(created_conv.conversation_id, async_db)
    assert fetched_conv.conversation_id == created_conv.conversation_id
    assert fetched_conv.title == "Test Conversation"


@pytest.mark.asyncio
async def test_delete_conversation(async_db: AsyncSession, db_user):
    knowledge = Knowledge(
        name="Test Knowledge", knowledge_path="/path/to/knowledge", user_id=db_user.user_id
    )
    async_db.add(knowledge)
    await async_db.commit()
    await async_db.refresh(knowledge)
    conv_in = schemas.ConversationCreate(
        title="Test Conversation", knowledge_id=knowledge.knowledge_id
    )
    created_conv = await service.create_conversation(conv_in, db_user.user_id, async_db)
    conv_id = created_conv.conversation_id
    await service.delete_conversation(conv_id, async_db)
    with pytest.raises(exceptions.ConversationNotFoundException):
        await service.get_conversation_by_id(conv_id, async_db)
