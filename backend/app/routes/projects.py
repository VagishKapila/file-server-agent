# backend/app/routes/projects.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# Import the actual shared db module (same as vendors)
from .. import db

router = APIRouter(tags=["projects"])


class ProjectIn(BaseModel):
    name: str
    city: Optional[str] = None
    notes: Optional[str] = None


class ProjectUpdate(BaseModel):
    id: int
    notes: Optional[str] = None


# --------------------------
# GET ALL PROJECTS
# --------------------------
@router.get("/")
async def get_projects():

    if db.pool is None:
        await db.connect_to_db()

    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM projects ORDER BY id DESC")
        return [dict(r) for r in rows]


# --------------------------
# ADD PROJECT
# --------------------------
@router.post("/add")
async def add_project(data: ProjectIn):

    if db.pool is None:
        await db.connect_to_db()

    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO projects (name, city, notes)
            VALUES ($1, $2, $3)
            """,
            data.name,
            data.city,
            data.notes
        )

        rows = await conn.fetch("SELECT * FROM projects ORDER BY id DESC")
        return [dict(r) for r in rows]


# --------------------------
# UPDATE PROJECT
# --------------------------
@router.post("/update")
async def update_project(data: ProjectUpdate):

    if db.pool is None:
        await db.connect_to_db()

    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE projects SET notes = $1 WHERE id = $2",
            data.notes,
            data.id
        )

        row = await conn.fetchrow(
            "SELECT * FROM projects WHERE id = $1",
            data.id
        )

        return dict(row)


# --------------------------
# REMOVE PROJECT
# --------------------------
@router.post("/remove")
async def remove_project(data: dict):

    project_id = data.get("id")
    if not project_id:
        raise HTTPException(status_code=400, detail="Missing id")

    if db.pool is None:
        await db.connect_to_db()

    async with db.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM projects WHERE id = $1",
            project_id
        )

        return {"status": "deleted", "id": project_id}