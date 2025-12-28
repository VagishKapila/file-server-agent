import io
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from app.services.storage_service import upload_bytes


def generate_project_report_pdf(report_data: dict) -> dict:
    """
    Generates a project PDF IN MEMORY and uploads to R2.
    """

    # ---------------- SAFETY CHECKS ----------------
    if not report_data or not isinstance(report_data, dict):
        raise ValueError("report_data is empty or invalid")

    project_request_id = report_data.get("project_request_id")
    if not project_request_id:
        raise ValueError("project_request_id missing from report_data")

    subcontractors = report_data.get("subcontractors") or []
    if not isinstance(subcontractors, list):
        raise ValueError("subcontractors must be a list")

    materials = report_data.get("materials") or []
    if not isinstance(materials, list):
        raise ValueError("materials must be a list")

    # ---------------- PDF SETUP ----------------
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    y = height - 50

    # ---------------- HEADER ----------------
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Project Outreach Report")
    y -= 30

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Project Request ID: {project_request_id}")
    y -= 30

    # ---------------- SUBCONTRACTORS ----------------
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Subcontractors")
    y -= 20

    pdf.setFont("Helvetica", 10)

    for sub in subcontractors:
        if not isinstance(sub, dict):
            continue

        lines = [
            f"- {sub.get('company', '—')} ({sub.get('trade', '—')})",
            f"  Open to Bid: {sub.get('open_to_bid', '—')}",
            f"  Job Walk: {sub.get('job_walk', '—')}",
            f"  Bid Turnaround: {sub.get('bid_turnaround_days', '—')} days",
            f"  Notes: {sub.get('summary', '—')}",
        ]

        for line in lines:
            if y < 80:
                pdf.showPage()
                pdf.setFont("Helvetica", 10)
                y = height - 50

            pdf.drawString(60, y, line)
            y -= 14

        y -= 10

    # ---------------- MATERIALS ----------------
    if materials:
        if y < 120:
            pdf.showPage()
            y = height - 50

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Materials")
        y -= 20

        pdf.setFont("Helvetica", 10)

        for m in materials:
            if not isinstance(m, dict):
                continue

            lines = [
                f"- {m.get('vendor', '—')} ({m.get('category', '—')})",
                f"  Price: {m.get('price', '—')} {m.get('currency', '')}",
                f"  Lead Time: {m.get('lead_time_days', '—')} days",
            ]

            for line in lines:
                if y < 80:
                    pdf.showPage()
                    pdf.setFont("Helvetica", 10)
                    y = height - 50

                pdf.drawString(60, y, line)
                y -= 14

            y -= 10

    # ---------------- SAVE & UPLOAD ----------------
    pdf.save()
    buffer.seek(0)

    filename = f"project_report_{project_request_id}.pdf"
    r2_key = f"reports/{project_request_id}/{filename}"

    r2_uri, size = upload_bytes(
        data=buffer.read(),
        key=r2_key,
        content_type="application/pdf",
    )

    return {
        "r2_uri": r2_uri,
        "r2_key": r2_key,
        "filename": filename,
        "file_size": size,
    }