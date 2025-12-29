from sqlalchemy import (
    Table, Column, Integer, Text, Boolean, JSON, TIMESTAMP
)
from sqlalchemy.sql import func
from app.db import Base

retell_call_audit = Table(
    "retell_call_audit",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("retell_call_id", Text, unique=True),
    Column("to_number", Text),
    Column("extracted_email", Text),
    Column("email_confirmed", Boolean),
    Column("project_request_id", Integer),
    Column("vendor_call_id", Integer),
    Column("raw_payload", JSON),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now()),
)