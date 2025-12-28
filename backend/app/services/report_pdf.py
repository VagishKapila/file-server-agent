import io
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from app.services.storage_service import upload_bytes


def generate_project_report_pdf(report_data: dict) -> dict:
    """
    Generates a project PDF IN MEMORY and uploads to R2.

    Returns:
        {
            "r2_key": str,
            "file_size": int,
            "filename": str
        }
    """

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    y = height - 50

    # ---------------- HEADER ----------------
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Project Outreach Report")
    y -= 30

    pdf.setFont("Helvetica", 11)
    pdf.drawString(
        50,
        y,
        f"Project Request ID: {report_data.get('project_request_id')}",
    )
    y -= 30

    # ---------------- SUBCONTRACTORS ----------------
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Subcontractors")
    y -= 20

    pdf.setFont("Helvetica", 10)
    for sub in report_data.get("subcontractors", []):
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
    materials = report_data.get("materials", [])
    if materials:
        if y < 120:
            pdf.showPage()
            y = height - 50

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Materials")
        y -= 20

        pdf.setFont("Helvetica", 10)
        for m in materials:
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

    pdf.save()
    buffer.seek(0)

    filename = f"project_report_{report_data['project_request_id']}.pdf"
    r2_key = f"reports/{report_data['project_request_id']}/{filename}"

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
