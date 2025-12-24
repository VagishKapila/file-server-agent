from sqlalchemy import Column, Integer, String, DateTime, func
from app.db import Base


class VendorContact(Base):
    __tablename__ = "vendor_contacts"

    id = Column(Integer, primary_key=True, index=True)
    vendor_name = Column(String, nullable=True)
    vendor_phone = Column(String, index=True, nullable=False)
    email = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
