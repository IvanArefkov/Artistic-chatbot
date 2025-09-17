from sqlalchemy import String, Text, DateTime, Index, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime
from typing import List
import uuid

class Base(DeclarativeBase):
    pass


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now()
    )


    # One-to-many relationship with ChatMessage
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ChatSession(id='{self.id}', title='{self.title}')>"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    # Primary key - UUID for distributed systems
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Foreign key to ChatSession
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True
    )

    # Who sent the message (user, assistant, system, etc.)
    sender: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )

    # Message content - using Text for potentially long messages
    content: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    # When the message was created
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        index=True
    )

    # Many-to-one relationship with ChatSession
    session: Mapped["ChatSession"] = relationship(
        "ChatSession",
        back_populates="messages"
    )

    # Composite indexes for common query patterns
    __table_args__ = (
        # For getting messages in a session ordered by time
        Index('ix_session_created', 'session_id', 'created_at'),
        # For getting messages by sender in a session
        Index('ix_session_sender', 'session_id', 'sender'),
    )

    def __repr__(self):
        return f"<ChatMessage(id='{self.id}', session='{self.session_id}', sender='{self.sender}')>"
