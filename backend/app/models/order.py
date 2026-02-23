from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base

class OrderSide(str, enum.Enum):
    buy = "buy"
    sell = "sell"

class OrderType(str, enum.Enum):
    limit = "limit"
    market = "market"

class OrderStatus(str, enum.Enum):
    open = "open"
    filled = "filled"
    cancelled = "cancelled"

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pair = Column(String(20), nullable=False)
    side = Column(Enum(OrderSide), nullable=False)
    type = Column(Enum(OrderType), nullable=False)
    price = Column(Numeric(precision=20, scale=8), nullable=True)
    quantity = Column(Numeric(precision=20, scale=8), nullable=False)
    filled_quantity = Column(Numeric(precision=20, scale=8), default=0)
    status = Column(Enum(OrderStatus), default=OrderStatus.open)
    is_bot_order = Column(Boolean, default=False)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="orders")
    trades = relationship("Trade", back_populates="order")

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    price = Column(Numeric(precision=20, scale=8), nullable=False)
    quantity = Column(Numeric(precision=20, scale=8), nullable=False)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="trades")
