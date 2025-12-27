from sqlalchemy import Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.sql import func
from app.db import Base


class ProjectFile(Base):
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True)
    project_request_id = Column(Integer, index=True)
    filename = Column(String)
    stored_path = Column(String)        # ✅ SINGLE SOURCE OF TRUTH
    file_type = Column(String)
    file_size = Column(Integer)
    checksum = Column(String)
    shared = Column(Boolean, default=False)

    uploaded_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )