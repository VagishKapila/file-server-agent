from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.db import Base

class VendorCall(Base):
    __tablename__ = "vendor_calls"

    id = Column(Integer, primary_key=True)
    project_request_id = Column(Integer, index=True)
    trade = Column(String, index=True)

    vendor_id = Column(String, index=True)
    vendor_name = Column(String)
    vendor_phone = Column(String)

    is_preferred = Column(Boolean, default=False)

    status = Column(String, default="pending")
    # pending | called | confirmed | declined | no_answer | failed

    confirmed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
