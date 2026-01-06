from typing import List, Dict, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ============================================================
# VendorAnchor
# Purpose:
# - Global vendor reuse across projects/devices
# - Avoid repeated Google/Yelp calls
# - Speed + cost control
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


def _anchor_key(name: str, phone: str | None) -> Tuple[str, str]:
    return (
        _normalize_name(name),
        phone or "",
    )


# ------------------------------------------------------------
# Fetch anchored vendors (global reuse)
# ------------------------------------------------------------
async def fetch_anchored_vendors(
    db: AsyncSession,
    trades: List[str],
    limit: int = 50,
) -> List[Dict]:

    rows = await db.execute(
        text("""
            SELECT
                vendor_name,
                trade,
                phone,
                email,
                source
            FROM search_results
            WHERE trade = ANY(:trades)
            ORDER BY id DESC
            LIMIT :limit
        """),
        {
            "trades": trades,
            "limit": limit,
        },
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


# ------------------------------------------------------------
# Merge anchors with live discovery
# ------------------------------------------------------------
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
