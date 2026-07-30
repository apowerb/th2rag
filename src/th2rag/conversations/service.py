from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.conversations import exceptions, schemas
from th2rag.models import Conversation
from th2rag.pagination import PageParams, PageResponse, paginate
from th2rag.users import schemas as user_schemas


async def get_all_conversations(
    page_params: PageParams, user: user_schemas.User, db: AsyncSession
) -> PageResponse[schemas.Conversation]:
    stmt = select(Conversation)
    if user.role != "ADMIN":
        stmt = stmt.where(Conversation.user_id == user.user_id)
    return await paginate(db, stmt, page_params, schemas.Conversation)


async def get_conversation_by_id(conversation_id: int, db: AsyncSession) -> schemas.Conversation:
    stmt = select(Conversation).where(Conversation.conversation_id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise exceptions.ConversationNotFoundException("Conversation not found")

    return schemas.Conversation.model_validate(conversation)


async def create_conversation(
    conversation_in: schemas.ConversationCreate, user_id: int, db: AsyncSession
) -> schemas.Conversation:
    new_conversation = Conversation(**conversation_in.model_dump(), user_id=user_id)

    db.add(new_conversation)
    await db.commit()
    await db.refresh(new_conversation)

    return schemas.Conversation.model_validate(new_conversation)


async def delete_conversation(conversation_id: int, db: AsyncSession) -> None:
    stmt = select(Conversation).where(Conversation.conversation_id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise exceptions.ConversationNotFoundException("Conversation not found")

    await db.delete(conversation)
    await db.commit()
