from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class DepositStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    failed = "failed"


class DepositTransaction(Base):
    __tablename__ = "deposit_transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tx_hash = Column(String(66), unique=True, nullable=False, index=True)
    amount_usdt = Column(Numeric(18, 6), nullable=False)
    from_address = Column(String(42), nullable=False)
    status = Column(Enum(DepositStatus), default=DepositStatus.pending)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="deposits")


class FeeIncome(Base):
    __tablename__ = "fee_income"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("bot_subscriptions.id"), nullable=False)
    amount_usdt = Column(Numeric(18, 2), nullable=False)
    period = Column(String(7), nullable=False)   # "2026-02"
    charged_at = Column(DateTime(timezone=True), server_default=func.now())
    settled_at = Column(DateTime(timezone=True), nullable=True)

    subscription = relationship("BotSubscription", back_populates="fee_income")
