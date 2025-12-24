from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)

    # AUTH PROVIDERS
    google_sub = Column(String, unique=True, nullable=True)
    provider = Column(String, nullable=False, default="google")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
