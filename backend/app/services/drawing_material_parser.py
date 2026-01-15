import os
import re
import json
import logging
from typing import List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
ENABLE_AI = os.getenv("ENABLE_AI_DRAWING_PARSER", "false").lower() == "true"

# ------------------------------------------------------------
# Fallback regex parser (NO AI)
# ------------------------------------------------------------
MATERIAL_RE = re.compile(
    r"(concrete|rebar|steel|electrical|conduit|plumbing|hvac|tile|drywall|roofing)",
    re.I,
)

def fallback_parse(text: str) -> List[Dict]:
    found = set(m.lower() for m in MATERIAL_RE.findall(text))
    return [
        {
            "material": m,
            "quantity": None,
            "unit": None,
            "notes": "fallback-parser",
        }
        for m in found
    ]


# ------------------------------------------------------------
# AI Parser (isolated import)
# ------------------------------------------------------------
async def ai_parse(text: str) -> List[Dict]:
    try:
        from openai import OpenAI  # 🔒 IMPORT ONLY HERE
    except Exception as e:
        logger.warning("OpenAI not available, falling back", extra={"error": str(e)})
        return fallback_parse(text)

    client = OpenAI()

    prompt = f"""
You are a construction estimator.
Extract materials from this drawing text.

Return STRICT JSON ARRAY ONLY.
Each item:
{{
  "material": string,
  "quantity": number | null,
  "unit": string | null,
  "notes": string | null
}}

TEXT:
{text}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = resp.choices[0].message.content.strip()
        data = json.loads(content)

        if isinstance(data, list):
            return data

        logger.warning("AI response not list, fallback")
        return fallback_parse(text)

    except Exception as e:
        logger.exception("AI parse failed, fallback")
        return fallback_parse(text)


# ------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------
async def parse_drawing_to_materials(
    project_id: int,
    drawing_text: str,
    db: AsyncSession,
) -> List[Dict]:
    """
    Parse drawing text into materials.
    Uses AI if enabled, otherwise regex fallback.
    Saves material_requests rows.
    """

    materials = (
        await ai_parse(drawing_text)
        if ENABLE_AI
        else fallback_parse(drawing_text)
    )

    # Persist materials
    for m in materials:
        await db.execute(
            text("""
                INSERT INTO material_requests
                (
                    project_request_id,
                    source,
                    status
                )
                VALUES
                (
                    :pid,
                    'drawing',
                    'open'
                )
            """),
            {"pid": project_id},
        )

    await db.commit()

    logger.info(
        "Drawing parsed",
        extra={
            "project_id": project_id,
            "material_count": len(materials),
            "ai_used": ENABLE_AI,
        },
    )

    return materials
