from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.sql import func
from app.models.vendor_call import VendorCall

async def finalize_call_once(
    *,
    db: AsyncSession,
    vendor_call_id: int,
) -> bool:
    """
    Returns True ONLY if this is the first time finalizing the call.
    Subsequent webhook events will be ignored.
    """

    res = await db.execute(
        select(VendorCall).where(VendorCall.id == vendor_call_id)
    )
    vc = res.scalar_one_or_none()

    if not vc:
        return False

    # 🔒 HARD GATE
    if vc.finalized_at is not None:
        return False

    await db.execute(
        update(VendorCall)
        .where(VendorCall.id == vendor_call_id)
        .values(finalized_at=func.now())
    )

    await db.commit()
    return True