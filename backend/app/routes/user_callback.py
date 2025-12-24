from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User

router = APIRouter(prefix="/user", tags=["user"])


class CallbackPayload(BaseModel):
    callback_name: str
    callback_phone: str


@router.post("/callback")
async def save_callback_info(
    payload: CallbackPayload,
    db: AsyncSession = Depends(get_db),
):
    # Beta assumption: single logged-in user
    user = (await db.execute(db.sync_session.query(User))).scalars().first()

    if not user:
        return {"error": "User not found"}

    user.callback_name = payload.callback_name
    user.callback_phone = payload.callback_phone

    await db.commit()

    return {"status": "saved"}
