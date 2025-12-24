from datetime import datetime, timedelta
import asyncio
import os
import requests

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import AsyncSessionLocal
from backend.app.models.activity_log import ActivityLog
from backend.app.models.vendor_call_state import VendorCallState

VAPI_CALL_ENDPOINT = "https://api.vapi.ai/call"

VAPI_PRIVATE_KEY = os.getenv("VAPI_PRIVATE_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")

MAX_RETRIES = 2
COOLDOWN_HOURS = 24


async def retry_failed_email_captures():
    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS)

        # 1️⃣ Find failed email captures
        result = await db.execute(
            select(ActivityLog)
            .where(ActivityLog.action == "email_capture_failed")
            .where(ActivityLog.created_at < cutoff)
        )

        failures = result.scalars().all()

        if not failures:
            print("ℹ️ No email_capture_failed records eligible for retry")
            return

        for fail in failures:
            payload = fail.payload or {}

            vendor_phone = payload.get("phone")
            trade = payload.get("trade")
            project_request_id = fail.project_id

            if not vendor_phone or not trade or not project_request_id:
                continue

            state_result = await db.execute(
                select(VendorCallState)
                .where(VendorCallState.project_request_id == project_request_id)
                .where(VendorCallState.vendor_phone == vendor_phone)
                .where(VendorCallState.trade == trade)
            )
            state = state_result.scalar_one_or_none()

            if not state:
                continue

            if state.attempts >= MAX_RETRIES:
                print(f"⛔ Max retries reached for {vendor_phone}")
                continue

            print(
                f"🔁 Retrying email capture | {vendor_phone} | attempt {state.attempts + 1}"
            )

            call_payload = {
                "assistantId": VAPI_ASSISTANT_ID,
                "phoneNumberId": VAPI_PHONE_NUMBER_ID,
                "customer": {"number": vendor_phone},
                "assistantOverrides": {
                    "firstMessage": (
                        "Hi, this is Jessica from BAINS Development. "
                        "I’m following up to send drawings and photos "
                        "for the project we discussed earlier. "
                        "What’s the best email to send them to?"
                    ),
                    "context": {
                        "primary_trade": trade,
                        "project_request_id": project_request_id,
                        "vendor_phone": vendor_phone,
                        "email_required": True,
                        "retry_attempt": state.attempts + 1,
                    },
                },
            }

            try:
                requests.post(
                    VAPI_CALL_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {VAPI_PRIVATE_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=call_payload,
                    timeout=15,
                )
            except Exception as e:
                print(f"❌ Retry call failed: {e}")
                continue

            state.attempts += 1
            state.last_attempt_at = datetime.utcnow()

        await db.commit()
        print("✅ Retry job completed")


if __name__ == "__main__":
    asyncio.run(retry_failed_email_captures())