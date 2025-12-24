from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from backend.app.db import Base


# -----------------------------
# SQLAlchemy ORM MODEL ONLY
# -----------------------------

class ProjectRequest(Base):
    __tablename__ = "project_requests"

    id = Column(Integer, primary_key=True)
    project_name = Column(String, nullable=False)
    location = Column(String)
    request_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)