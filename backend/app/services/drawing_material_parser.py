import openai
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

openai.api_key = None  # uses env var

PROMPT = """
You are a construction takeoff assistant.
Extract materials from the drawing.
Return JSON:
[
  { "material": "", "quantity": number, "unit": "", "notes": "" }
]
"""

async def parse_drawing_to_materials(
    project_id: int,
    drawing_text: str,
    db: AsyncSession,
):
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": drawing_text},
        ],
    )

    materials = eval(response.choices[0].message.content)

    for m in materials:
        await db.execute(
            text("""
                INSERT INTO material_requests
                (project_id, material_name, quantity, unit, notes)
                VALUES
                (:pid, :name, :qty, :unit, :notes)
            """),
            {
                "pid": project_id,
                "name": m["material"],
                "qty": m["quantity"],
                "unit": m["unit"],
                "notes": m.get("notes"),
            },
        )

    await db.commit()
    return materials
