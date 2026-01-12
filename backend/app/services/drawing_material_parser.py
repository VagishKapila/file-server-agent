"""
Placeholder for drawing → material intelligence.
Hooks OpenAI / vision / OCR later.
"""

async def parse_drawings_to_materials(
    project_id: int,
    file_paths: list[str],
):
    """
    Returns extracted materials from drawings
    """

    # TEMP MOCK — replace with OpenAI Vision / OCR pipeline
    return [
        {
            "material_name": "Porcelain Tile",
            "quantity": 1200,
            "unit": "sqft",
            "confidence": 0.82,
        },
        {
            "material_name": "Thinset Mortar",
            "quantity": 45,
            "unit": "bags",
            "confidence": 0.76,
        },
    ]
