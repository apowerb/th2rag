from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.conversations import exceptions, schemas, service
from th2rag.database import get_db
from th2rag.dependencies import get_current_user
from th2rag.users.schemas import User


async def get_conversation_or_404(
    conversation_id: int = Path(..., description="The ID of the conversation"),
    db: AsyncSession = Depends(get_db),
) -> schemas.Conversation:
    try:
        return await service.get_conversation_by_id(conversation_id, db)
    except exceptions.ConversationNotFoundException:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")


async def require_conversation_owner_or_admin(
    conversation: schemas.Conversation = Depends(get_conversation_or_404),
    current_user: User = Depends(get_current_user),
) -> schemas.Conversation:
    if (
        current_user.role != "ADMIN"
        and conversation.user_id is not None
        and conversation.user_id != current_user.user_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return conversation
