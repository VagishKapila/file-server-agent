from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Numeric,
    Text,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db import Base


class MaterialVendor(Base):
    __tablename__ = "material_vendors"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    company_name = Column(String, nullable=False)
    trade = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    country = Column(String, nullable=True)

    is_preferred = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    outreaches = relationship(
        "MaterialOutreach",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )


class MaterialOutreach(Base):
    __tablename__ = "material_outreach"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    project_request_id = Column(Integer, nullable=False)

    # 🔴 THIS MUST MATCH THE DB COLUMN NAME
    material_vendor_id = Column(
        Integer,
        ForeignKey("material_vendors.id"),
        nullable=False,
    )

    material_category = Column(String, nullable=True)
    status = Column(String, default="pending")
    confirmed_at = Column(DateTime, nullable=True)
    ai_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    vendor = relationship(
        "MaterialVendor",
        back_populates="outreaches",
        foreign_keys=[material_vendor_id],
    )

    quote = relationship(
        "MaterialQuote",
        uselist=False,
        back_populates="outreach",
        cascade="all, delete-orphan",
    )


class MaterialQuote(Base):
    __tablename__ = "material_quotes"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    outreach_id = Column(
        Integer,
        ForeignKey("material_outreach.id", ondelete="CASCADE"),
        nullable=False,
    )

    price = Column(Numeric, nullable=True)
    currency = Column(String, nullable=True)
    lead_time_days = Column(Integer, nullable=True)

    structured_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    outreach = relationship("MaterialOutreach", back_populates="quote")