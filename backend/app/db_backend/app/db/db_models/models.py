from sqlalchemy import (
    Column, String, Text, Boolean, Date, DateTime,
    Integer, Numeric, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from backend.app.db_backend.db import Base

def uid():
    return uuid.uuid4()

class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    location = Column(Text)
    country_code = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class ProjectRequest(Base):
    __tablename__ = "project_requests"
    id = Column(UUID, primary_key=True, default=uid)
    project_id = Column(UUID, ForeignKey("projects.id"))
    request_type = Column(String)  # sub | material
    bid_due_date = Column(Date)
    preferred_language = Column(String, default="en")
    created_at = Column(DateTime, default=datetime.utcnow)

class ProjectTrade(Base):
    __tablename__ = "project_trades"
    id = Column(UUID, primary_key=True, default=uid)
    project_request_id = Column(UUID, ForeignKey("project_requests.id"))
    trade_key = Column(String)

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(UUID, primary_key=True, default=uid)
    owner_type = Column(String)  # sub | material
    owner_id = Column(UUID)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
