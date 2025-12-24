from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.search_result import SearchResult

router = APIRouter(prefix="/projects", tags=["Project Search"])

@router.get("/{project_id}/search")
async def get_project_search(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SearchResult).where(
            SearchResult.project_request_id == project_id
        )
    )

    rows = result.scalars().all()

    return [
        {
            "vendor_name": r.vendor_name,
            "trade": r.trade,
            "phone": r.phone,
            "email": r.email,
            "source": r.source,
        }
        for r in rows
    ]
