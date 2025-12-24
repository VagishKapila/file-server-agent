# backend/app/routes/subs.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# Import shared db module (guaranteed single pool)
from .. import db

router = APIRouter(tags=["subs"])


# --------------------------
# MODELS
# --------------------------
class SubIn(BaseModel):
    name: str
    phone: Optional[str] = None
    trade: Optional[str] = None
    city: Optional[str] = None
    notes: Optional[str] = None


class SubUpdate(BaseModel):
    id: int
    notes: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    trade: Optional[str] = None


# --------------------------
# GET ALL SUBS
# --------------------------
@router.get("/")
async def get_subs():

    if db.pool is None:
        await db.connect_to_db()

    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM subs ORDER BY id DESC")
        return [dict(r) for r in rows]


# --------------------------
# ADD SUB
# --------------------------
@router.post("/add")
async def add_sub(data: SubIn):

    if db.pool is None:
        await db.connect_to_db()

    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO subs (name, phone, trade, city, notes)
            VALUES ($1, $2, $3, $4, $5)
            """,
            data.name,
            data.phone,
            data.trade,
            data.city,
            data.notes,
        )

        rows = await conn.fetch("SELECT * FROM subs ORDER BY id DESC")
        return [dict(r) for r in rows]


# --------------------------
# UPDATE SUB
# --------------------------
@router.post("/update")
async def update_sub(data: SubUpdate):

    if db.pool is None:
        await db.connect_to_db()

    # Build dynamic update set
    updates = []
    values = []

    if data.notes is not None:
        updates.append("notes = $" + str(len(values) + 1))
        values.append(data.notes)

    if data.phone is not None:
        updates.append("phone = $" + str(len(values) + 1))
        values.append(data.phone)

    if data.trade is not None:
        updates.append("trade = $" + str(len(values) + 1))
        values.append(data.trade)

    if data.city is not None:
        updates.append("city = $" + str(len(values) + 1))
        values.append(data.city)

    if not updates:
        raise HTTPException(status_code=400, detail="No update fields provided")

    # Append ID at the end
    values.append(data.id)

    query = f"UPDATE subs SET {', '.join(updates)} WHERE id = ${len(values)}"

    async with db.pool.acquire() as conn:
        await conn.execute(query, *values)

        row = await conn.fetchrow("SELECT * FROM subs WHERE id = $1", data.id)
        return dict(row)


# --------------------------
# REMOVE SUB
# --------------------------
@router.post("/remove")
async def remove_sub(data: dict):

    sub_id = data.get("id")
    if not sub_id:
        raise HTTPException(status_code=400, detail="Missing id")

    if db.pool is None:
        await db.connect_to_db()

    async with db.pool.acquire() as conn:
        await conn.execute("DELETE FROM subs WHERE id = $1", sub_id)

    return {"status": "deleted", "id": sub_id}