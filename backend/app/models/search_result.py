from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from backend.app.db import Base

class SearchResult(Base):
    __tablename__ = "search_results"

    id = Column(Integer, primary_key=True)
    project_request_id = Column(
        Integer,
        ForeignKey("project_requests.id"),
        nullable=False
    )

    vendor_name = Column(String, nullable=False)
    trade = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    source = Column(String, default="google")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
