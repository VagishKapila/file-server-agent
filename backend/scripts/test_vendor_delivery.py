import asyncio
from app.db_backend.db import get_db
from app.services.vendor_delivery import send_vendor_documents

PROJECT_REQUEST_ID = 203          # <-- use a real one with files
TEST_EMAIL = "test@vendor.com"    # dummy email

async def run_test():
    async for db in get_db():
        result = await send_vendor_documents(
            project_request_id=PROJECT_REQUEST_ID,
            vendor_email=TEST_EMAIL,
            db=db,
        )
        print("\n=== DELIVERY RESULT ===")
        print(result)
        break

if __name__ == "__main__":
    asyncio.run(run_test())
