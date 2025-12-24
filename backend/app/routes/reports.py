from app.db import get_db

from app.models.project import ProjectRequest

from app.models.subs import (
    Subcontractor,
    SubOutreach,
    SubCallResult,
    JobWalkSlot,
)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session


router = APIRouter(tags=["reports"])

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

@router.get("/project-basic/{project_request_id}")
async def project_basic_report(
    project_request_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProjectRequest).where(ProjectRequest.id == project_request_id)
    )
    pr = result.scalar_one_or_none()

    if not pr:
        raise HTTPException(status_code=404, detail="Project request not found")

    return {
        "project_request_id": pr.id,
        "project_name": pr.project_name,
        "location": pr.location,
        "request_type": pr.request_type,
        "created_at": pr.created_at,
    }

@router.get("/project/{project_request_id}")
def project_report(project_request_id: str, db: Session = Depends(get_db)):
    # ---- Subcontractors ----
    subs = (
        db.query(
            Subcontractor.company_name,
            Subcontractor.trade_key,
            SubOutreach.status,
            SubCallResult.open_to_bid,
            SubCallResult.wants_job_walk,
            SubCallResult.bid_turnaround_days,
            SubCallResult.summary
        )
        .join(SubOutreach, SubOutreach.subcontractor_id == Subcontractor.id)
        .join(SubCallResult, SubCallResult.outreach_id == SubOutreach.id)
        .filter(SubOutreach.project_request_id == project_request_id)
        .all()
    )

    sub_results = []
    for s in subs:
        sub_results.append({
            "company": s.company_name,
            "trade": s.trade_key,
            "status": s.status,
            "open_to_bid": s.open_to_bid,
            "job_walk": s.wants_job_walk,
            "bid_turnaround_days": s.bid_turnaround_days,
            "summary": s.summary
        })

    # ---- Job walk availability ----
    job_walks = (
        db.query(JobWalkSlot.availability_text)
        .join(SubOutreach, SubOutreach.id == JobWalkSlot.outreach_id)
        .filter(SubOutreach.project_request_id == project_request_id)
        .all()
    )

    # ---- Materials ----
    materials = (
        db.query(
            MaterialVendor.company_name,
            MaterialVendor.material_category,
            MaterialQuote.price,
            MaterialQuote.currency,
            MaterialQuote.lead_time_days
        )
        .join(MaterialOutreach, MaterialOutreach.vendor_id == MaterialVendor.id)
        .join(MaterialQuote, MaterialQuote.outreach_id == MaterialOutreach.id)
        .filter(MaterialOutreach.project_request_id == project_request_id)
        .all()
    )

    material_results = []
    for m in materials:
        material_results.append({
            "vendor": m.company_name,
            "category": m.material_category,
            "price": m.price,
            "currency": m.currency,
            "lead_time_days": m.lead_time_days
        })

    return {
        "project_request_id": project_request_id,
        "subcontractors": sub_results,
        "job_walk_availability": [j[0] for j in job_walks],
        "materials": material_results
    }
