from fpdf import FPDF

def generate_project_report_pdf(report_data: dict, output_path: str):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Project Outreach Report", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"Project Request ID: {report_data['project_request_id']}", ln=True)

    # ---- Subcontractors ----
    pdf.ln(6)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Subcontractors", ln=True)

    pdf.set_font("Arial", size=10)
    for sub in report_data["subcontractors"]:
        pdf.multi_cell(
            0, 6,
            f"- {sub['company']} ({sub['trade']})\n"
            f"  Open to Bid: {sub['open_to_bid']}\n"
            f"  Job Walk: {sub['job_walk']}\n"
            f"  Bid Turnaround: {sub['bid_turnaround_days']} days\n"
            f"  Notes: {sub['summary']}\n"
        )

    # ---- Materials ----
    if report_data["materials"]:
        pdf.ln(4)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Materials", ln=True)

        pdf.set_font("Arial", size=10)
        for m in report_data["materials"]:
            pdf.multi_cell(
                0, 6,
                f"- {m['vendor']} ({m['category']})\n"
                f"  Price: {m['price']} {m['currency']}\n"
                f"  Lead Time: {m['lead_time_days']} days\n"
            )

    pdf.output(output_path)
cat << 'EOF' > backend/app/routes/report_export.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid
import os

from app.db_backend.db import get_db
from app.routes.reports import project_report
from app.services.report_pdf import generate_project_report_pdf

router = APIRouter(prefix="/report-export", tags=["Report Export"])

@router.get("/project/{project_request_id}")
def export_project_report_pdf(project_request_id: str, db: Session = Depends(get_db)):
    report_data = project_report(project_request_id, db)

    filename = f"project_report_{project_request_id}.pdf"
    output_path = os.path.join("/tmp", filename)

    generate_project_report_pdf(report_data, output_path)

    return {
        "status": "ok",
        "file_path": output_path,
        "filename": filename
    }
