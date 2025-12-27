import os
from fpdf import FPDF

# Canonical upload root (same one used by uploader + email)
UPLOAD_ROOT = os.getenv("UPLOAD_DIR", "/app/bains_uploads")


def generate_project_report_pdf(report_data: dict, output_path: str):
    """
    Generates a project outreach PDF and writes it to output_path.
    output_path MUST be a persistent path under UPLOAD_DIR.
    """

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ---- Header ----
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Project Outreach Report", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", size=11)
    pdf.cell(
        0,
        8,
        f"Project Request ID: {report_data['project_request_id']}",
        ln=True,
    )

    # ---- Subcontractors ----
    pdf.ln(6)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Subcontractors", ln=True)

    pdf.set_font("Arial", size=10)
    for sub in report_data.get("subcontractors", []):
        pdf.multi_cell(
            0,
            6,
            f"- {sub.get('company', '—')} ({sub.get('trade', '—')})\n"
            f"  Open to Bid: {sub.get('open_to_bid', '—')}\n"
            f"  Job Walk: {sub.get('job_walk', '—')}\n"
            f"  Bid Turnaround: {sub.get('bid_turnaround_days', '—')} days\n"
            f"  Notes: {sub.get('summary', '—')}\n",
        )

    # ---- Materials ----
    materials = report_data.get("materials", [])
    if materials:
        pdf.ln(4)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Materials", ln=True)

        pdf.set_font("Arial", size=10)
        for m in materials:
            pdf.multi_cell(
                0,
                6,
                f"- {m.get('vendor', '—')} ({m.get('category', '—')})\n"
                f"  Price: {m.get('price', '—')} {m.get('currency', '')}\n"
                f"  Lead Time: {m.get('lead_time_days', '—')} days\n",
            )

    # ---- Write PDF (persistent path) ----
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pdf.output(output_path)