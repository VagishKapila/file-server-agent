from sqlalchemy import Column, Integer, String
from app.db import Base

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    company = Column(String)
    trade = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    city = Column(String)
    country = Column(String)
    created_by = Column(String)