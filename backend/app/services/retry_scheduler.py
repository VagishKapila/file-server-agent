"""
Retry scheduler DISABLED (temporary).

Reason:
- We are stabilizing the system and debugging VAPI keys.
- Retry logic will be re-enabled later with correct signatures.

This file MUST export retry_loop to avoid import errors.
"""

import asyncio

async def retry_loop():
    # Intentionally disabled
    print("⚠️ retry_loop is disabled — skipping")
    while True:
        await asyncio.sleep(3600)