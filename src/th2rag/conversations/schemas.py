from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    pass

    # from th2rag.messages.schemas import Message
    # from th2rag.knowledge.schemas import Knowledge


class ConversationBase(BaseModel):
    """
    Shared properties for a Conversation.
    """

    knowledge_id: int | None = None
    dataset_id: int | None = None
    title: str


class ConversationCreate(ConversationBase):
    """
    Schema for creating a new Conversation.
    Inherits from ConversationBase; can add extra fields if needed.
    """

    pass


class Conversation(ConversationBase):
    """
    Schema for reading a Conversation (e.g. GET requests).
    Includes DB-generated fields like IDs, timestamps, etc.
    """

    conversation_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
