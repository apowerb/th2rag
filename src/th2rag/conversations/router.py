from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.conversations import dependencies, schemas, service
from th2rag.database import get_db
from th2rag.dependencies import get_current_user
from th2rag.messages.router import router as messages_router
from th2rag.pagination import PageParams, PageResponse
from th2rag.users import schemas as user_schemas

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=PageResponse[schemas.Conversation])
async def get_all_conversations(
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    return await service.get_all_conversations(page_params, current_user, db)


@router.post("", response_model=schemas.Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_in: schemas.ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    return await service.create_conversation(conversation_in, current_user.user_id, db)


@router.get("/{conversation_id}", response_model=schemas.Conversation)
async def get_conversation_by_id(
    conversation: schemas.Conversation = Depends(dependencies.require_conversation_owner_or_admin),
):
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation: schemas.Conversation = Depends(dependencies.require_conversation_owner_or_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_conversation(conversation.conversation_id, db)


router.include_router(messages_router, prefix="/{conversation_id}/messages", tags=["messages"])
