from sqlalchemy import Column, Integer, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.db import Base

class BetaSubscriber(Base):
    __tablename__ = "beta_subscribers"

    id = Column(Integer, primary_key=True)
    name = Column(Text)
    trade = Column(Text)
    phone = Column(Text, unique=True, nullable=False)
    email = Column(Text)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
