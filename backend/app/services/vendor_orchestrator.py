# app/services/vendor_orchestrator.py
"""
Vendor Orchestrator
-------------------
Pure decision layer:
- Collect vendors from preferred, drawing, DB, Google/Yelp
- Normalize + rank
- Decide language + call/email eligibility
NO outreach. NO DB mutation (except optional reads).
"""

from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.match_engine import match_vendors
from app.services.vendor_reputation import get_vendor_scores
from app.services.multilang_email_builder import detect_language
from app.routes.vendors import get_preferred_vendors_for_user


async def orchestrate_vendors(
    *,
    db: AsyncSession,
    project_request_id: int,
    user_id: int,
    trades: List[str],
    address: Optional[str],
    request_type: str,
) -> List[Dict]:
    """
    Returns ordered vendor candidates with metadata for UI + outreach layer.
    """

    vendors: List[Dict] = []

    # 1️⃣ Preferred vendors (highest priority)
    preferred = await get_preferred_vendors_for_user(db, user_id)
    for v in preferred:
        vendors.append({
            "vendor_id": f"preferred:{v['id']}",
            "name": v["name"],
            "trade": v["trade"],
            "email": None,
            "phone": v["phone"],
            "source": "preferred",
        })

    # 2️⃣ Discovered vendors (DB + Google + Yelp)
    discovered = await match_vendors(
        db=db,
        trades=trades,
        location=address,
    )

    for d in discovered:
        vendors.append({
            "vendor_id": f"search:{d['id']}",
            "name": d["vendor_name"],
            "trade": d["trade"],
            "email": d.get("email"),
            "phone": d.get("phone"),
            "source": d.get("source", "google"),
        })

    # 3️⃣ Reputation / response scoring
    scores = await get_vendor_scores(db, trades)

    enriched = []
    for v in vendors:
        score = scores.get(v["name"], 50)

        language = detect_language(
            email=v.get("email"),
            phone=v.get("phone"),
            source=v.get("source"),
        )

        callable_flag = bool(v.get("phone")) and language == "en"

        enriched.append({
            **v,
            "language": language,
            "callable": callable_flag,
            "auto_queued": True,
            "visible": True,
            "priority_score": score,
        })

    # 4️⃣ Final ordering
    enriched.sort(
        key=lambda x: (
            x["source"] != "preferred",
            not x["callable"],
            -x["priority_score"],
        )
    )

    return enriched
