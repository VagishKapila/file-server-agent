# EOF: app/services/vendor_orchestrator.py

import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.match_engine import match_engine_safe

logger = logging.getLogger(__name__)


async def orchestrate_vendors(
    *,
    db: AsyncSession,
    project_request_id: int,
    user_id: int,
    trades: List[str],
    address: str | None,
    request_type: str = "commercial",
) -> List[Dict[str, Any]]:
    """
    Vendor discovery ONLY.
    No calls, no emails, no WhatsApp.
    """

    logger.info(
        "Vendor orchestration started",
        extra={
            "project_request_id": project_request_id,
            "user_id": user_id,
            "trades": trades,
            "address": address,
            "request_type": request_type,
        },
    )

    # Normalize trades
    clean_trades = [t.strip() for t in trades if t and t.strip()]
    if not clean_trades:
        return []

    # Discover vendors
    vendors = await match_engine_safe(
        db=db,
        trades=clean_trades,
        address=address,
        project_request_id=project_request_id,
    )

    # Safe flags (no outreach yet)
    for v in vendors:
        v["auto_queued"] = True
        v["outreach_enabled"] = False

    logger.info(
        "Vendor orchestration complete",
        extra={"count": len(vendors)},
    )

    return vendors