from fastapi import APIRouter, HTTPException, Form
from pydantic import BaseModel
import asyncpg

router = APIRouter()

# -------------------------------------
# DATABASE CONNECTION (local Postgres)
# -------------------------------------
async def get_conn():
    return await asyncpg.connect(
        user="vagkapi",
        database="vkfield",
        host="127.0.0.1",
        port=5432
    )

# -------------------------------------
# MODELS
# -------------------------------------
class VendorCreate(BaseModel):
    user_id: str
    name: str
    phone: str | None = None
    trade: str | None = None
    source: str | None = "manual"

# -------------------------------------
# ADD VENDOR
# -------------------------------------
@router.post("/preferred/add")
async def add_vendor(vendor: VendorCreate):
    try:
        conn = await get_conn()
        await conn.execute(
            """
            INSERT INTO preferred_vendors (user_id, name, phone, trade, source)
            VALUES ($1, $2, $3, $4, $5)
            """,
            vendor.user_id,
            vendor.name,
            vendor.phone,
            vendor.trade,
            vendor.source
        )
        await conn.close()
        return {"status": "ok", "message": "Vendor added"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------
# LIST VENDORS FOR A USER
# -------------------------------------
@router.get("/preferred/list/{user_id}")
async def list_vendors(user_id: str):
    try:
        conn = await get_conn()
        rows = await conn.fetch(
            """
            SELECT id, name, phone, trade, source, created_at
            FROM preferred_vendors
            WHERE user_id = $1
            ORDER BY created_at DESC
            """, 
            user_id
        )
        await conn.close()
        return {"vendors": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------
# DELETE A VENDOR
# -------------------------------------
@router.delete("/preferred/delete/{vendor_id}")
async def delete_vendor(vendor_id: int):
    try:
        conn = await get_conn()
        await conn.execute(
            "DELETE FROM preferred_vendors WHERE id = $1",
            vendor_id
        )
        await conn.close()
        return {"status": "ok", "message": "Vendor deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
