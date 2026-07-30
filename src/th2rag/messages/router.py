from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.conversations.dependencies import require_conversation_owner_or_admin
from th2rag.conversations.schemas import Conversation
from th2rag.database import get_db
from th2rag.dependencies import get_rag_service
from th2rag.messages import exceptions, schemas, service
from th2rag.pagination import PageParams, PageResponse
from th2rag.rag.services.rag_service import RAGService

router = APIRouter(tags=["messages"])


@router.get("", response_model=PageResponse[schemas.Message])
async def get_all_messages(
    conversation: Conversation = Depends(require_conversation_owner_or_admin),
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_all_messages(conversation.conversation_id, page_params, db)


@router.get("/{message_id}", response_model=schemas.Message)
async def get_message_by_id(
    message_id: Annotated[int, Path(description="The ID of the message")],
    conversation: Conversation = Depends(require_conversation_owner_or_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.get_message_by_id(conversation.conversation_id, message_id, db)
    except exceptions.MessageNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=schemas.Message)
async def create_message(
    message_in: schemas.MessageCreate,
    conversation: Conversation = Depends(require_conversation_owner_or_admin),
    db: AsyncSession = Depends(get_db),
    rag_service: RAGService = Depends(get_rag_service),
):
    # Don't inject rag_service as dependency - let service handle it conditionally
    return await service.create_and_respond_message(
        conversation.conversation_id, message_in=message_in, db=db,rag_service=rag_service
    )


@router.post("/{message_id}/feedback", response_model=schemas.Message)
async def add_feedback_to_message(
    feedback_in: schemas.FeedbackCreate,
    message_id: Annotated[int, Path(description="The ID of the message")],
    conversation: Conversation = Depends(require_conversation_owner_or_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.add_feedback_to_message(
            conversation.conversation_id, message_id, feedback_in, db
        )
    except exceptions.MessageNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))