from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.db import Base


class VendorCall(Base):
    __tablename__ = "vendor_calls"

    id = Column(Integer, primary_key=True)

    # -----------------------------
    # CORE RELATION FIELDS
    # -----------------------------
    project_request_id = Column(Integer, index=True)
    trade = Column(String, index=True)

    vendor_id = Column(String, index=True)
    vendor_name = Column(String)
    vendor_phone = Column(String, index=True)

    # -----------------------------
    # RETELL LINK
    # -----------------------------
    retell_call_id = Column(String, index=True)

    # -----------------------------
    # STATUS / FLAGS
    # -----------------------------
    is_preferred = Column(Boolean, default=False)

    # pending | called | confirmed | declined | no_answer | failed | completed
    status = Column(String, default="pending")

    confirmed_at = Column(DateTime, nullable=True)

    # 🔒 FINALIZATION GATE (CRITICAL)
    finalized_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())