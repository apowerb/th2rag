import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.messages import schemas, service
from th2rag.models import Conversation, Knowledge
from th2rag.pagination import PageParams


class DummyRAGService:
    def answer_question(self, question: str, doc_id: int, limit: int) -> str:
        return "This is a dummy answer."


@pytest.mark.asyncio
async def test_get_all_messages_empty(async_db: AsyncSession):
    knowledge = Knowledge(name="Test Knowledge", knowledge_path="/path/to/knowledge")
    async_db.add(knowledge)
    await async_db.commit()
    await async_db.refresh(knowledge)
    conv = Conversation(knowledge_id=knowledge.knowledge_id, title="Test Conversation")
    async_db.add(conv)
    await async_db.commit()
    await async_db.refresh(conv)
    page_params = PageParams(page=1, size=10)
    page_response = await service.get_all_messages(
        conversation_id=conv.conversation_id, page_params=page_params, db=async_db
    )
    assert hasattr(page_response, "results")
    assert len(page_response.results) == 0


@pytest.mark.asyncio
async def test_create_message(async_db: AsyncSession):
    knowledge = Knowledge(name="Test Knowledge", knowledge_path="/path/to/knowledge")
    async_db.add(knowledge)
    await async_db.commit()
    await async_db.refresh(knowledge)
    conv = Conversation(knowledge_id=knowledge.knowledge_id, title="Test Conversation")
    async_db.add(conv)
    await async_db.commit()
    await async_db.refresh(conv)
    conversation_id = conv.conversation_id
    message_in = schemas.MessageCreate(content="Hello World", sender="USER")
    created_message = await service.create_message(conversation_id, message_in, async_db)
    assert created_message.content == "Hello World"
    assert created_message.sender == "USER"
    assert created_message.conversation_id == conversation_id


@pytest.mark.asyncio
async def test_get_message_by_id(async_db: AsyncSession):
    knowledge = Knowledge(name="Test Knowledge", knowledge_path="/path/to/knowledge")
    async_db.add(knowledge)
    await async_db.commit()
    await async_db.refresh(knowledge)
    conv = Conversation(knowledge_id=knowledge.knowledge_id, title="Test Conversation")
    async_db.add(conv)
    await async_db.commit()
    await async_db.refresh(conv)
    conversation_id = conv.conversation_id
    message_in = schemas.MessageCreate(content="Test message", sender="USER")
    created_message = await service.create_message(conversation_id, message_in, async_db)
    fetched_message = await service.get_message_by_id(
        conversation_id, created_message.message_id, async_db
    )
    assert fetched_message.message_id == created_message.message_id
    assert fetched_message.content == "Test message"


@pytest.mark.asyncio
async def test_create_and_respond_message(async_db: AsyncSession):
    knowledge = Knowledge(name="Test Knowledge", knowledge_path="/path/to/knowledge")
    async_db.add(knowledge)
    await async_db.commit()
    await async_db.refresh(knowledge)
    conv = Conversation(knowledge_id=knowledge.knowledge_id, title="Test Conversation")
    async_db.add(conv)
    await async_db.commit()
    await async_db.refresh(conv)
    conversation_id = conv.conversation_id
    user_message_in = schemas.MessageCreate(content="What is AI?", sender="USER")
    dummy_rag = DummyRAGService()
    system_message = await service.create_and_respond_message(
        conversation_id, user_message_in, dummy_rag, async_db
    )
    assert system_message.sender == "SYSTEM"
    assert system_message.content == "This is a dummy answer."


@pytest.mark.asyncio
async def test_add_feedback_to_message(async_db: AsyncSession):
    knowledge = Knowledge(name="Test Knowledge", knowledge_path="/path/to/knowledge")
    async_db.add(knowledge)
    await async_db.commit()
    await async_db.refresh(knowledge)
    conv = Conversation(knowledge_id=knowledge.knowledge_id, title="Test Conversation")
    async_db.add(conv)
    await async_db.commit()
    await async_db.refresh(conv)
    conversation_id = conv.conversation_id
    message_in = schemas.MessageCreate(content="Test feedback message", sender="USER")
    created_message = await service.create_message(conversation_id, message_in, async_db)
    feedback_in = schemas.FeedbackCreate(feedback_type="A", like=True, reason="Good message")
    updated_message = await service.add_feedback_to_message(
        conversation_id, created_message.message_id, feedback_in, async_db
    )
    assert updated_message.feedback is not None
    assert updated_message.feedback.feedback_type == "A"
    assert updated_message.feedback.like is True
    assert updated_message.feedback.reason == "Good message"
