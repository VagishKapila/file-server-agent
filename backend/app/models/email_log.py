from sqlalchemy import Column, Integer, Text, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func

from app.db import Base


class EmailLog(Base):
    __tablename__ = "email_log"

    id = Column(Integer, primary_key=True, index=True)

    project_request_id = Column(
        Integer,
        ForeignKey("project_requests.id", ondelete="CASCADE"),
        nullable=False,
    )

    recipient_email = Column(Text, nullable=False)

    email_type = Column(
        Text,
        nullable=False,  # 'subcontractor' | 'client'
    )

    related_call_id = Column(Text, nullable=True)

    sent_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
