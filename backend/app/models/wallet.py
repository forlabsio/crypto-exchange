from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    asset = Column(String(20), nullable=False)
    balance = Column(Numeric(precision=20, scale=8), default=0)
    locked_balance = Column(Numeric(precision=20, scale=8), default=0)

    user = relationship("User", back_populates="wallets")
