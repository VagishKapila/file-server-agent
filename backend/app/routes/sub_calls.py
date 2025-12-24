from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from datetime import datetime

from backend.app.db import get_db
from backend.app.models.subs import (
    Subcontractor,
    SubOutreach,
    SubCallResult,
    JobWalkSlot,
)

router = APIRouter(prefix="/sub-calls", tags=["Sub Calls"])

MAX_CONFIRMED_PER_TRADE = 3


# ---------- REQUEST SCHEMA ----------

class SubCallPayload(BaseModel):
    project_request_id: int
    trade: str

    company_name: str
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    state: str | None = None

    open_to_bid: bool
    wants_job_walk: bool = False
    bid_turnaround_days: int | None = None

    availability: list[str] = []
    ai_summary: str | None = None
    extra_notes: str | None = None


# ---------- HELPERS ----------

async def confirmed_count(
    db: AsyncSession,
    project_request_id: int,
    trade: str,
):
    stmt = (
        select(func.count(SubOutreach.id))
        .where(
            SubOutreach.project_request_id == project_request_id,
            SubOutreach.trade == trade,
            SubOutreach.status == "confirmed",
        )
    )
    res = await db.execute(stmt)
    return res.scalar() or 0


# ---------- ENDPOINT ----------

@router.post("/")
async def save_sub_call(
    payload: SubCallPayload,
    db: AsyncSession = Depends(get_db),
):
    # 1️⃣ Lookup subcontractor
    stmt = (
        select(Subcontractor)
        .where(
            Subcontractor.name == payload.company_name,
            Subcontractor.trade == payload.trade,
        )
    )
    res = await db.execute(stmt)
    sub = res.scalar_one_or_none()

    if not sub:
        sub = Subcontractor(
            name=payload.company_name,
            trade=payload.trade,
            phone=payload.phone,
            email=payload.email,
            city=payload.city,
            state=payload.state,
        )
        db.add(sub)
        await db.flush()

    # 2️⃣ Hard stop (B5 limit logic)
    count = await confirmed_count(
        db,
        payload.project_request_id,
        payload.trade,
    )

    if not sub.is_preferred and count >= MAX_CONFIRMED_PER_TRADE:
        return {
            "status": "stopped",
            "reason": "confirmation_limit_reached",
            "confirmed_count": count,
        }

    # 3️⃣ Prevent duplicate confirmed subcontractor
    stmt = (
        select(SubOutreach)
        .where(
            SubOutreach.project_request_id == payload.project_request_id,
            SubOutreach.subcontractor_id == sub.id,
            SubOutreach.trade == payload.trade,
            SubOutreach.status == "confirmed",
        )
    )
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        return {"status": "ignored", "reason": "already_confirmed"}

    # 4️⃣ Save outreach
    outreach = SubOutreach(
        project_request_id=payload.project_request_id,
        subcontractor_id=sub.id,
        trade=payload.trade,
        status="confirmed" if payload.open_to_bid else "declined",
        confirmed_at=datetime.utcnow() if payload.open_to_bid else None,
        ai_summary=payload.ai_summary,
    )
    db.add(outreach)
    await db.flush()

    # 5️⃣ Save call result
    result = SubCallResult(
        outreach_id=outreach.id,
        open_to_bid=payload.open_to_bid,
        wants_job_walk=payload.wants_job_walk,
        bid_turnaround_days=payload.bid_turnaround_days,
        extra_notes=payload.extra_notes,
        structured_payload=payload.dict(),
    )
    db.add(result)

    # 6️⃣ Save job walk availability
    for slot in payload.availability:
        db.add(
            JobWalkSlot(
                outreach_id=outreach.id,
                availability_text=slot,
            )
        )

    # 7️⃣ Commit once
    await db.commit()

    return {
        "status": outreach.status,
        "subcontractor_id": sub.id,
        "outreach_id": outreach.id,
        "confirmed_at": outreach.confirmed_at,
    }