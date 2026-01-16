from typing import List, Dict, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Vendor Anchor Helpers
# ============================================================

def _normalize_name(name: str | None) -> str:
    return (
        (name or "")
        .lower()
        .replace(",", "")
        .replace(".", "")
        .replace("&", "and")
        .strip()
    )

def _anchor_key(name: str | None, phone: str | None) -> Tuple[str, str]:
    return (_normalize_name(name), phone or "")

# ============================================================
# Vendor Reputation Signals (SAFE NO-OP FOR NOW)
# ============================================================

async def record_vendor_signal(
    db: AsyncSession,
    *,
    vendor_email: str,
    project_request_id: int,
    signal_type: str,
    signal_value: float | None = None,
    meta: Dict | None = None,
):
    """
    Records a vendor reputation signal.

    This is intentionally lightweight for v1.
    Safe to call even if scoring logic is not active yet.
    """

    try:
        await db.execute(
            text("""
                INSERT INTO vendor_scores
                (vendor_email, project_request_id, signal_type, signal_value, meta)
                VALUES (:email, :pid, :stype, :svalue, :meta)
            """),
            {
                "email": vendor_email,
                "pid": project_request_id,
                "stype": signal_type,
                "svalue": signal_value,
                "meta": meta,
            },
        )
        await db.commit()

    except Exception as e:
        # NEVER crash ingestion because of reputation tracking
        logger.warning(
            "Vendor signal not recorded",
            extra={
                "vendor_email": vendor_email,
                "project_request_id": project_request_id,
                "signal_type": signal_type,
                "error": str(e),
            },
        )

# ============================================================
# Existing Anchor Logic (UNCHANGED)
# ============================================================

def apply_vendor_reputation(vendors: list) -> list:
    return vendors

async def fetch_anchored_vendors(
    db: AsyncSession,
    trades: List[str],
    limit: int = 50,
) -> List[Dict]:

    rows = await db.execute(
        text("""
            SELECT vendor_name, trade, phone, email, source
            FROM search_results
            WHERE trade = ANY(:trades)
            ORDER BY id DESC
            LIMIT :limit
        """),
        {"trades": trades, "limit": limit},
    )

    vendors = []
    seen = set()

    for r in rows.fetchall():
        key = _anchor_key(r.vendor_name, r.phone)
        if key in seen:
            continue
        seen.add(key)

        vendors.append({
            "name": r.vendor_name,
            "trade": r.trade,
            "phone": r.phone,
            "email": r.email,
            "callable": bool(r.phone),
            "preferred": False,
            "same_city": False,
            "source": r.source or "db_anchor",
        })

    return vendors

def merge_with_anchors(
    anchors: List[Dict],
    live_results: List[Dict],
) -> List[Dict]:

    merged = []
    seen = set()

    for v in anchors + live_results:
        key = _anchor_key(v.get("name"), v.get("phone"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(v)

    return merged
# --------------------------------------------------
# SAFE STUB: Vendor Reputation (Phase 0)
# --------------------------------------------------

async def get_vendor_scores(
    *,
    db,
    vendor_emails: list[str],
):
    """
    Phase 0 stub.
    Returns neutral scores for all vendors.

    Later phases will:
    - use response rates
    - email/call success
    - language match
    - project relevance
    """

    return {
        email: {
            "score": 0,
            "response_rate": None,
            "preferred": False,
        }
        for email in vendor_emails
    }

