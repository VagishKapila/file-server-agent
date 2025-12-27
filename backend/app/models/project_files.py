from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from app.db import Base


class ProjectFile(Base):
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True, index=True)

    project_request_id = Column(Integer, index=True, nullable=False)

    filename = Column(String, nullable=False)

    # ✅ SINGLE SOURCE OF TRUTH — LOCAL FILE PATH ONLY
    stored_path = Column(String, nullable=False)

    file_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    checksum = Column(String, nullable=True)

    shared = Column(Boolean, default=False)

    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )