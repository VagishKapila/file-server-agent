from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy.sql import func
from backend.app.db import Base

class VendorCallState(Base):
    __tablename__ = "vendor_call_state"

    id = Column(Integer, primary_key=True)
    project_request_id = Column(Integer, index=True)
    vendor_phone = Column(Text)
    trade = Column(Text)
    attempts = Column(Integer, default=0)
    status = Column(Text)  # pending | voicemail | interested | completed | failed
    last_attempt_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
