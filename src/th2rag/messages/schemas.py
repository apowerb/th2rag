from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict


class Sender(str, Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"


class MessageType(str, Enum):
    TEXT = "TEXT"
    SCRIPT = "SCRIPT"


class FeedbackType(str, Enum):
    A = "A"
    B = "B"
    OTHER = "OTHER"


if TYPE_CHECKING:
    pass


class MessageBase(BaseModel):
    conversation_id: int | None = None
    content: str
    sender: Sender


class MessageCreate(MessageBase):
    pass


class Message(MessageBase):
    message_id: int
    type: MessageType
    created_at: datetime
    updated_at: datetime
    # feedback: Optional["Feedback"] = Field(default=None)

    model_config = ConfigDict(from_attributes=True)


class FeedbackBase(BaseModel):
    message_id: int | None = None
    feedback_type: FeedbackType | None
    like: bool | None = None
    reason: str | None = None


class FeedbackCreate(FeedbackBase):
    pass


class Feedback(FeedbackBase):
    feedback_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


Message.model_rebuild()
Feedback.model_rebuild()
