from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"  # Should be plural

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # For MVP, maybe make name optional? They might not tell us initially
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Better name for WhatsApp context, with index for fast lookups
    whatsapp_number: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )

    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # Auto-update when record changes
    )

    total_interactions: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Lead qualification fields
    lead_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default="new"
    )  # Options: new, warm, hot, qualified, customer, lost

    ready_to_purchase: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationship to conversations (one customer has many conversations)
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="customer"
    )

    def __repr__(self) -> str:
        return (
            f"<Customer(whatsapp_number='{self.whatsapp_number}', name='{self.name}')>"
        )


class Conversation(Base):
    __tablename__ = "conversations"  # Should be plural

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Use Text for longer messages (WhatsApp can be up to 4096 chars)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(  # Fixed typo: create_at -> created_at
        DateTime(timezone=True), server_default=func.now()
    )

    # Foreign key should reference UUID type, not string
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )

    # Who sent this message: "customer" or "assistant"
    sender_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # Values: "customer" or "assistant"

    # Optional: Store Twilio message ID for tracking
    twilio_message_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationship back to customer (many conversations belong to one customer)
    customer: Mapped["Customer"] = relationship(
        "Customer", back_populates="conversations"
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation(sender='{self.sender_type}', "
            f"message='{self.message[:30]}...', date='{self.created_at}')>"
        )
