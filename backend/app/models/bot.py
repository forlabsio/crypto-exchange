from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base

class BotStatus(str, enum.Enum):
    active = "active"
    evicted = "evicted"

class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    strategy_config = Column(JSON, default={})
    status = Column(Enum(BotStatus), default=BotStatus.active)
    max_drawdown_limit = Column(Numeric(5, 2), default=20.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    evicted_at = Column(DateTime(timezone=True), nullable=True)

    subscriptions = relationship("BotSubscription", back_populates="bot")
    performance = relationship("BotPerformance", back_populates="bot")

class BotSubscription(Base):
    __tablename__ = "bot_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="bot_subscriptions")
    bot = relationship("Bot", back_populates="subscriptions")

class BotPerformance(Base):
    __tablename__ = "bot_performance"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    period = Column(String(7), nullable=False)
    win_rate = Column(Numeric(5, 2), default=0)
    monthly_return_pct = Column(Numeric(10, 4), default=0)
    max_drawdown_pct = Column(Numeric(5, 2), default=0)
    total_trades = Column(Integer, default=0)

    bot = relationship("Bot", back_populates="performance")
