from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from io import BytesIO
from datetime import datetime

from app.db import get_db
from app.models.project import ProjectRequest

# ---- Optional imports (never assumed) ----
try:
    from app.models.subs import Subcontractor, SubOutreach
except Exception:
    Subcontractor = SubOutreach = None

try:
    from app.models.materials import (
        MaterialVendor,
        MaterialOutreach,
        MaterialQuote,
    )
except Exception:
    MaterialVendor = MaterialOutreach = MaterialQuote = None

# ---- PDF ----
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

router = APIRouter(tags=["report-export"])


@router.get("/project/{project_request_id}")
async def export_project_pdf(
    project_request_id: int,
    db: AsyncSession = Depends(get_db),
):
    # =====================================================
    # FETCH PROJECT (ONLY HARD GUARANTEE)
    # =====================================================
    result = await db.execute(
        select(ProjectRequest).where(ProjectRequest.id == project_request_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # =====================================================
    # SAFE FETCH — SUBCONTRACTORS
    # =====================================================
    subcontractors = []
    if Subcontractor and SubOutreach:
        try:
            result = await db.execute(
                select(Subcontractor, SubOutreach)
                .join(
                    SubOutreach,
                    SubOutreach.subcontractor_id == Subcontractor.id,
                )
                .where(SubOutreach.project_request_id == project_request_id)
            )
            subcontractors = result.all()
        except Exception:
            subcontractors = []

    # =====================================================
    # SAFE FETCH — MATERIALS
    # =====================================================
    materials = []
    if MaterialVendor and MaterialOutreach:
        try:
            result = await db.execute(
                select(MaterialVendor, MaterialQuote)
                .join(
                    MaterialOutreach,
                    MaterialOutreach.vendor_id == MaterialVendor.id,
                )
                .outerjoin(
                    MaterialQuote,
                    MaterialQuote.outreach_id == MaterialOutreach.id,
                )
                .where(MaterialOutreach.project_request_id == project_request_id)
            )
            materials = result.all()
        except Exception:
            materials = []

    # =====================================================
    # CREATE PDF (NEVER FAILS)
    # =====================================================
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    # -----------------------------
    # PAGE 1 — PROJECT
    # -----------------------------
    y = height - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Project Report")
    y -= 30

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Project Name: {project.project_name}")
    y -= 18
    pdf.drawString(50, y, f"Location: {project.location or '—'}")
    y -= 18
    pdf.drawString(50, y, f"Request Type: {project.request_type}")
    y -= 18
    pdf.drawString(50, y, f"Created At: {project.created_at}")
    y -= 25
    pdf.drawString(50, y, f"Generated On: {datetime.utcnow()}")

    # -----------------------------
    # PAGE 2 — SUBCONTRACTORS
    # -----------------------------
    pdf.showPage()
    y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Subcontractors")
    y -= 25
    pdf.setFont("Helvetica", 11)

    if not subcontractors:
        pdf.drawString(50, y, "No subcontractor responses recorded yet.")
    else:
        for sub, outreach in subcontractors:
            pdf.drawString(50, y, f"Company: {getattr(sub, 'name', '—')}")
            y -= 15
            pdf.drawString(70, y, f"Trade: {getattr(sub, 'trade', '—')}")
            y -= 15
            pdf.drawString(70, y, f"Status: {getattr(outreach, 'status', '—')}")
            y -= 25

            if y < 100:
                pdf.showPage()
                y = height - 50
                pdf.setFont("Helvetica", 11)

    # -----------------------------
    # PAGE 3 — MATERIALS
    # -----------------------------
    pdf.showPage()
    y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Materials")
    y -= 25
    pdf.setFont("Helvetica", 11)

    if not materials:
        pdf.drawString(50, y, "No material responses recorded yet.")
    else:
        for vendor, quote in materials:
            pdf.drawString(50, y, f"Vendor: {getattr(vendor, 'name', '—')}")
            y -= 15
            pdf.drawString(
                70,
                y,
                f"Category: {getattr(vendor, 'material_category', '—')}",
            )
            y -= 15

            if quote:
                price = getattr(quote, "price", "—")
                currency = getattr(quote, "currency", "")
                lead = getattr(quote, "lead_time_days", "—")
                pdf.drawString(
                    70,
                    y,
                    f"Price: {price} {currency} | Lead Time: {lead} days",
                )
                y -= 20
            else:
                pdf.drawString(70, y, "No quote submitted yet.")
                y -= 20

            if y < 100:
                pdf.showPage()
                y = height - 50
                pdf.setFont("Helvetica", 11)

    # -----------------------------
    # FINALIZE
    # -----------------------------
    pdf.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=project_{project_request_id}.pdf"
        },
    )