from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db import Base


class Subcontractor(Base):
    __tablename__ = "subcontractors"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    trade = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    is_preferred = Column(Boolean, default=False)  # ✅ ADD THIS

    created_at = Column(DateTime, default=datetime.utcnow)

    outreaches = relationship("SubOutreach", back_populates="subcontractor")


class SubOutreach(Base):
    """
    ONE ROW = ONE CALL / AI OUTREACH ATTEMPT
    """
    __tablename__ = "sub_outreaches"

    id = Column(Integer, primary_key=True)

    project_request_id = Column(Integer, nullable=False)
    subcontractor_id = Column(Integer, ForeignKey("subcontractors.id"))

    trade = Column(String, nullable=False)

    status = Column(
        String,
        default="pending",  
        # pending | called | confirmed | declined | no_answer | stopped
    )

    confirmed_at = Column(DateTime, nullable=True)

    call_attempt = Column(Integer, default=1)

    ai_summary = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    subcontractor = relationship("Subcontractor", back_populates="outreaches")
    result = relationship("SubCallResult", uselist=False, back_populates="outreach")
    job_walk_slots = relationship("JobWalkSlot", back_populates="outreach")


class SubCallResult(Base):
    """
    NORMALIZED CALL RESULT DATA
    """
    __tablename__ = "sub_call_results"

    id = Column(Integer, primary_key=True)
    outreach_id = Column(Integer, ForeignKey("sub_outreaches.id"))

    open_to_bid = Column(Boolean, default=False)
    wants_job_walk = Column(Boolean, default=False)
    bid_turnaround_days = Column(Integer, nullable=True)

    extra_notes = Column(Text, nullable=True)

    structured_payload = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    outreach = relationship("SubOutreach", back_populates="result")


class JobWalkSlot(Base):
    __tablename__ = "job_walk_slots"

    id = Column(Integer, primary_key=True)
    outreach_id = Column(Integer, ForeignKey("sub_outreaches.id"))

    availability_text = Column(String, nullable=False)

    outreach = relationship("SubOutreach", back_populates="job_walk_slots")
