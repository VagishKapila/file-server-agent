from sqlalchemy import Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.sql import func
from backend.app.db import Base


class ProjectFile(Base):
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True)
    project_request_id = Column(Integer, index=True, nullable=False)

    filename = Column(Text, nullable=False)            # original
    stored_filename = Column(Text, nullable=False)     # uuid
    stored_path = Column(Text, nullable=False)         # full disk path

    file_type = Column(Text)                           # MIME
    file_size = Column(Integer)
    checksum = Column(Text)
    shared = Column(Boolean, default=False)

    uploaded_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )