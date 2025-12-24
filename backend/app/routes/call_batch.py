from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db import get_db
from app.models.vendor_call import VendorCall

router = APIRouter(prefix="/call-batch", tags=["Call Batch"])


@router.post("/start")
async def start_call_batch(
    project_request_id: int,
    trade: str,
    vendors: list[dict],
    db: AsyncSession = Depends(get_db),
):
    # Count confirmed vendors for this trade
    confirmed_count = await db.scalar(
        select(func.count())
        .select_from(VendorCall)
        .where(
            VendorCall.project_request_id == project_request_id,
            VendorCall.trade == trade,
            VendorCall.status == "confirmed",
        )
    )

    if confirmed_count >= 3:
        return {
            "status": "stopped",
            "reason": "3 vendors already confirmed",
        }

    created = 0

    for v in vendors:
        if confirmed_count + created >= 3:
            break

        call = VendorCall(
            project_request_id=project_request_id,
            trade=trade,
            vendor_id=v["id"],
            vendor_name=v["name"],
            vendor_phone=v["phone"],
            is_preferred=v.get("preferred", False),
            status="pending",
        )
        db.add(call)
        created += 1

    await db.commit()

    return {
        "status": "started",
        "trade": trade,
        "calls_created": created,
    }
