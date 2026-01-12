from fastapi import APIRouter, UploadFile, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.drawing_material_parser import parse_drawing_to_materials

router = APIRouter(prefix="/drawings", tags=["Drawings"])

@router.post("/parse/{project_id}")
async def parse_drawing(
    project_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")

    materials = await parse_drawing_to_materials(
        project_id=project_id,
        drawing_text=text,
        db=db,
    )

    return {"materials": materials}
