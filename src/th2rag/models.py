import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from th2rag.config import settings
from th2rag.database import Base
from th2rag.rag.constants import DEFAULT_PROMPT


class Sender(enum.Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"


class FeebackType(enum.Enum):
    A = "A"
    B = "B"
    OTHER = "OTHER"


class UserRole(enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"


class Status(enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MessageType(enum.Enum):
    TEXT = "TEXT"
    SCRIPT = "SCRIPT"

class User(Base):
    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=True)
    role = Column(
        Enum(UserRole, name="role_enum", schema=settings.db_schema),
        nullable=False,
        default=UserRole.USER,
    )
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    conversations = relationship("Conversation", back_populates="user")
    knowledges = relationship("Knowledge", back_populates="user")
    datasets = relationship("Dataset", back_populates="user")
    llm_config=relationship("UserLLMConfig", back_populates="user", uselist=False)

    def __repr__(self):
        return f"<User(user_id={self.user_id}, email={self.email})>"


class Conversation(Base):
    __tablename__ = "conversation"

    conversation_id = Column(Integer, primary_key=True)
    knowledge_id = Column(
        Integer, ForeignKey("knowledge.knowledge_id", ondelete="SET NULL"), nullable=True
    )
    dataset_id = Column(
        Integer, ForeignKey("Dataset.dataset_id", ondelete="SET NULL"), nullable=True
    )
    user_id = Column(Integer, ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan", passive_deletes=True
    )
    knowledge = relationship("Knowledge", back_populates="conversations")
    dataset = relationship("Dataset", back_populates="conversations")

    def __repr__(self):
        return f"<Conversation(conversation_id={self.conversation_id})>"


class Message(Base):
    __tablename__ = "message"

    message_id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer, ForeignKey("conversation.conversation_id", ondelete="CASCADE"), nullable=False
    )
    content = Column(Text, nullable=False)
    sender = Column(Enum(Sender, name="sender_enum", schema=settings.db_schema), nullable=False)
    type = Column(Enum(MessageType, name="type_enum", schema=settings.db_schema), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    feedback = relationship("Feedback", uselist=False, back_populates="message")
    sources = relationship("Source", back_populates="message")

    def __repr__(self):
        return f"<Message(message_id={self.message_id})>"


class Source(Base):
    __tablename__ = "source"

    source_id = Column(Integer, primary_key=True)
    message_id = Column(
        Integer, ForeignKey("message.message_id", ondelete="CASCADE"), nullable=False
    )
    source_path = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    message = relationship("Message", back_populates="sources")

    def __repr__(self):
        return f"<Source(source_id={self.source_id}, name={self.source_path})>"


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id = Column(
        Integer, ForeignKey("message.message_id", ondelete="CASCADE"), primary_key=True
    )
    feedback_type = Column(
        Enum(FeebackType, name="feedback_enum", schema=settings.db_schema), nullable=True
    )
    like = Column(Boolean, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    message = relationship("Message", back_populates="feedback")

    def __repr__(self):
        return f"<Feedback(feedback_id={self.feedback_id})>"


class Knowledge(Base):
    __tablename__ = "knowledge"

    knowledge_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(Status, name="status_enum", schema=settings.db_schema),
        nullable=False,
        default=Status.PENDING,
    )
    prompt = Column(Text, default=DEFAULT_PROMPT)
    knowledge_path = Column(String(255), nullable=False)
    # Changed from Text to JSONB for better performance and querying
    knowledge_paths = Column(JSONB, nullable=True)
    filenames = Column(JSONB, nullable=True)
    user_id = Column(Integer, ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    callback_url = Column(String(2048), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    conversations = relationship("Conversation", back_populates="knowledge")
    user = relationship("User", back_populates="knowledges")

    def __repr__(self):
        return f"<Knowledge(knowledge_id={self.knowledge_id}, name={self.name})>"


class Dataset(Base):
    __tablename__ = "Dataset"

    dataset_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    n_columns = Column(Integer, nullable=False)
    n_rows = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    column_types = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    conversations = relationship("Conversation", back_populates="dataset")
    user = relationship("User", back_populates="datasets")

    def __repr__(self):
        return f"<Dataset(dataset_id={self.dataset_id}, name={self.name})>"



class UserLLMConfig(Base):
    __tablename__ = "user_llm_config"

    config_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(100), nullable=False)
    model_name = Column(String(100), nullable=False)
    api_key = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="llm_config")
    
    def __repr__(self):
        return f"<UserLLMConfig(config_id={self.config_id}, user_id={self.user_id})>"