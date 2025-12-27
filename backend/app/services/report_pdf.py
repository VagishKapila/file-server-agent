import os
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

# Canonical upload root
UPLOAD_ROOT = os.getenv("UPLOAD_DIR", "/app/bains_uploads")


def generate_project_report_pdf(report_data: dict, output_path: str):
    """
    Generates a project outreach PDF using reportlab
    and writes it to a persistent path under UPLOAD_DIR.
    """

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    pdf = canvas.Canvas(output_path, pagesize=LETTER)
    width, height = LETTER

    y = height - 50

    # ---- Header ----
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

    # ---- Subcontractors ----
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

    # ---- Materials ----
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