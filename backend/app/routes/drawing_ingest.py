from fastapi import APIRouter, UploadFile, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.drawing_material_parser import parse_drawing_to_materials
from app.services.vendor_orchestrator import orchestrate_vendors

router = APIRouter(prefix="/drawings", tags=["Drawings"])


@router.post("/parse/{project_id}")
async def parse_drawing(
    project_id: int,
    file: UploadFile,

    # 🔹 optional but UI-ready
    user_id: int | None = Form(None),
    address: str | None = Form(None),
    request_type: str = Form("commercial"),

    db: AsyncSession = Depends(get_db),
):
    # 1️⃣ Read drawing
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")

    # 2️⃣ Parse materials from drawing
    materials = await parse_drawing_to_materials(
        project_id=project_id,
        drawing_text=text,
        db=db,
    )

    # 3️⃣ Discover vendors (NO outreach)
    vendors = await orchestrate_vendors(
        db=db,
        project_request_id=project_id,
        user_id=user_id,
        trades=[m["material"] for m in materials if m.get("material")],
        address=address,
        request_type=request_type,
    )

    # 4️⃣ Return UI-ready payload
    return {
        "project_id": project_id,
        "request_type": request_type,
        "materials": materials,
        "vendors": vendors,
    }