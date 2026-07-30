import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from th2rag.conversations import (
    exceptions as conversations_exceptions,
)
from th2rag.conversations import (
    service as conversations_service,
)
from th2rag.dataset import service as dataset_service
from th2rag.messages import exceptions, schemas
from th2rag.models import Feedback, Knowledge, Message
from th2rag.pagination import PageParams, PageResponse, paginate
from th2rag.rag.services.rag_service import RAGService
from th2rag.utils.helpers import build_script_generation_prompt, construct_history
from th2rag.dependencies import get_rag_service
from fastapi import HTTPException
from th2rag.rag.services.rag_service import RAGService



async def get_all_messages(
    conversation_id: int, page_params: PageParams, db: AsyncSession
) -> PageResponse[schemas.Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .options(selectinload(Message.conversation))
        .options(selectinload(Message.feedback))
    )
    return await paginate(db, stmt, page_params, schemas.Message)


async def get_message_by_id(
    conversation_id: int, message_id: int, db: AsyncSession
) -> schemas.Message:
    stmt = (
        select(Message)
        .where(
            Message.message_id == message_id,
            Message.conversation_id == conversation_id,
        )
        .options(selectinload(Message.feedback))
    )
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()
    if not message:
        raise exceptions.MessageNotFoundException(
            "Message not found or does not belong to the conversation"
        )
    return schemas.Message.model_validate(message)


async def create_message(
    conversation_id: int, message_in: schemas.MessageCreate, db: AsyncSession
) -> schemas.Message:
    try:
        current_conversation = await conversations_service.get_conversation_by_id(
            conversation_id, db
        )
        new_message = Message(
            conversation_id=conversation_id, content=message_in.content, sender=message_in.sender
        )
        db.add(new_message)
        await db.commit()
        await db.refresh(new_message)
        set_committed_value(new_message, "feedback", None)
        return schemas.Message.model_validate(new_message)

    except conversations_exceptions.ConversationNotFoundException as e:
        raise e




async def create_and_respond_message(
    conversation_id: int,
    message_in: schemas.MessageCreate,
    db: AsyncSession,
    rag_service: RAGService, 
) -> schemas.Message:
    # Récupération de la conversation
    conversation = await conversations_service.get_conversation_by_id(
        conversation_id=conversation_id, db=db
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check knowledge status BEFORE loading models or processing anything
    if conversation.knowledge_id:
        stmt = select(Knowledge).where(Knowledge.knowledge_id == conversation.knowledge_id)
        result = await db.execute(stmt)
        knowledge = result.scalar_one_or_none()
        if knowledge and knowledge.status.value in ["FAILED"]:
            raise HTTPException(
                status_code=422, 
                detail="The knowledge base could not be processed and is unavailable. Please try again or create a new knowledge base."
            )
        if knowledge and knowledge.status.value in ["PENDING"]:
            raise HTTPException(
                status_code=202, 
                detail="The knowledge base is currently being processed. Please wait a moment and try again."
            )

    # Récupération de l'historique
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    history = construct_history(messages=messages)



    if conversation.dataset_id:
        dataset = await dataset_service.get_dataset_by_id(dataset_id=conversation.dataset_id, db=db)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        prompt = build_script_generation_prompt(message_in.content, dataset.column_types)

        try:
            llm_output = rag_service.generate_code_snippet(
                question=message_in.content, prompt=prompt, history=history
            )
            parsed_output = json.loads(llm_output)
            generated_text = parsed_output.get("script")
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="LLM did not return valid JSON")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Script generation failed: {str(e)}")

        message_type = schemas.MessageType.SCRIPT

    else:
        # MODE = text
        doc_id = conversation.knowledge_id
        prompt = "You are a helpful assistant"
        if doc_id:
            stmt = select(Knowledge).where(Knowledge.knowledge_id == doc_id)
            result = await db.execute(stmt)
            knowledge = result.scalar_one_or_none()
            if knowledge:
                prompt = knowledge.prompt

        try:
            generated_text = rag_service.answer_question(
                question=message_in.content, doc_id=doc_id, limit=3, prompt=prompt, history=history
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Response generation failed: {str(e)}")

        message_type = schemas.MessageType.TEXT

    # Créer le message utilisateur
    user_message = Message(
        conversation_id=conversation_id,
        content=message_in.content,
        sender=message_in.sender,
        type=schemas.MessageType.TEXT,
    )
    db.add(user_message)

    # Créer le message système
    system_message = Message(
        conversation_id=conversation_id,
        content=generated_text,
        sender=schemas.Sender.SYSTEM,
        type=message_type,
    )
    db.add(system_message)

    await db.commit()
    await db.refresh(system_message)
    return schemas.Message.model_validate(system_message)


async def add_feedback_to_message(
    conversation_id: int, message_id: int, feedback_in: schemas.FeedbackCreate, db: AsyncSession
) -> schemas.Message:
    stmt = select(Message).where(
        Message.message_id == message_id, Message.conversation_id == conversation_id
    )
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()
    if not message:
        raise exceptions.MessageNotFoundException(
            "Message not found or does not belong to the conversation"
        )

    new_feedback = Feedback(
        feedback_id=message.message_id,
        feedback_type=feedback_in.feedback_type,
        like=feedback_in.like,
        reason=feedback_in.reason,
    )
    message.feedback = new_feedback

    db.add(new_feedback)
    await db.commit()
    await db.refresh(message)

    return schemas.Message.model_validate(message)