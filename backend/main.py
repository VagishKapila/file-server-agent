from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import asyncio
from pathlib import Path

from backend.app.db import connect_to_db, close_db_connection
from backend.app.routes.auth import router as auth_router
from backend.app.routes.auth_google import router as auth_google_router
from backend.app.routes import (
    subs_routes,
    projects,
    vendors,
    autodial,
    activity,
    project_requests,
    material_requests,
    reports,
    report_export,
    material_calls,
)
from backend.app.routes.sub_calls import router as sub_calls_router
from backend.app.routes.search_routes import router as search_router
from backend.app.routes.project_search import router as project_search_router
from backend.modules.vendors.routes.vendor_routes import router as vendor_router
from backend.app.routes.negotiator_webhook import router as negotiator_router
from backend.app.routes.browser_test import router as browser_test_router
from backend.app.routes.project_files import router as project_files_router
from backend.app.routes.subcontractor_email import router as subcontractor_email_router
from backend.app.routes.client_email import router as client_email_router
from backend.app.routes.client_report import router as client_report_router
from backend.app.routes.project_report import router as project_report_router
from backend.app.routes.user_profile import router as user_profile_router
from backend.app.routes.admin_beta import router as admin_beta_router
from backend.app.services.retry_scheduler import retry_loop

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

app = FastAPI(title="Jessica Sub AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(auth_google_router)
app.include_router(subs_routes.router, prefix="/subs")
app.include_router(projects.router, prefix="/projects")
app.include_router(vendors.router, prefix="/vendors")
app.include_router(vendor_router)
app.include_router(project_requests.router)
app.include_router(sub_calls_router, prefix="/sub-calls")
app.include_router(search_router, prefix="/api")
app.include_router(project_search_router)
app.include_router(autodial.router)
app.include_router(activity.router, prefix="/activity")
app.include_router(material_requests.router, prefix="/material-requests")
app.include_router(material_calls.router)
app.include_router(reports.router, prefix="/reports")
app.include_router(report_export.router, prefix="/report-export")
app.include_router(browser_test_router)
app.include_router(negotiator_router)
app.include_router(project_files_router)
app.include_router(subcontractor_email_router)
app.include_router(client_email_router)
app.include_router(client_report_router)
app.include_router(project_report_router)
app.include_router(user_profile_router)
app.include_router(admin_beta_router)

print("🔥 RUNNING backend.app.main 🔥")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/__fingerprint")
def fingerprint():
    return {"status": "correct app loaded"}

@app.on_event("startup")
async def startup():
    await connect_to_db()
    asyncio.create_task(retry_loop())

@app.on_event("shutdown")
async def shutdown():
    await close_db_connection()
