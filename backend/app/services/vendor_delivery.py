from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.file_delivery import prepare_files_for_vendor
from app.services.email_sender import send_email


async def send_vendor_documents(
    *,
    project_request_id: int,
    vendors: List[Dict],
    db: AsyncSession,
) -> Dict:
    """
    Final delivery orchestrator (MULTI-VENDOR SAFE).

    - Supports 1 → N vendors (email per vendor)
    - Decides attach vs link vs none ONCE
    - Sends independently (safe retries + logging)
    - Future-ready for WhatsApp routing
    """

    if not vendors:
        return {"sent": False, "reason": "no_vendors"}

    # 🔹 Prepare files ONCE per project
    file_info = await prepare_files_for_vendor(
        project_request_id=project_request_id,
        db=db,
    )

    subject = "Project Documents & Scope Information"
    results = []

    for vendor in vendors:
        vendor_email = vendor.get("email")
        vendor_name = vendor.get("name", "Vendor")
        contact_route = vendor.get("contact_route", "email")

        if not vendor_email:
            results.append({
                "vendor": vendor_name,
                "sent": False,
                "reason": "missing_email",
            })
            continue

        # 🚧 WhatsApp routing placeholder (B already flags it)
        if contact_route == "whatsapp":
            results.append({
                "vendor": vendor_name,
                "sent": False,
                "route": "whatsapp",
                "reason": "whatsapp_not_enabled_yet",
            })
            continue

        # -------- EMAIL PATH --------

        if file_info["mode"] == "none":
            body = f"""
            Hi {vendor_name},<br><br>

            There are no files attached for this project yet.
            We will follow up shortly if anything is added.<br><br>

            Thanks,<br>
            Project Team
            """

            send_email(
                to_email=vendor_email,
                subject=subject,
                html_body=body,
                attachments=[],
            )

            results.append({
                "vendor": vendor_name,
                "sent": True,
                "mode": "none",
            })
            continue

        if file_info["mode"] == "attach":
            attachments = [f["stored_path"] for f in file_info["files"]]

            body = f"""
            Hi {vendor_name},<br><br>

            Please find the project documents attached.<br>
            Total size: {file_info.get("total_mb")} MB<br><br>

            Thanks,<br>
            Project Team
            """

            send_email(
                to_email=vendor_email,
                subject=subject,
                html_body=body,
                attachments=attachments,
            )

            results.append({
                "vendor": vendor_name,
                "sent": True,
                "mode": "attach",
                "files": len(attachments),
            })
            continue

        # mode == link
        links = [f["stored_path"] for f in file_info["files"]]
        link_list = "<br>".join(links)

        body = f"""
        Hi {vendor_name},<br><br>

        The project files are available at the links below:<br><br>
        {link_list}<br><br>

        Thanks,<br>
        Project Team
        """

        send_email(
            to_email=vendor_email,
            subject=subject,
            html_body=body,
            attachments=[],
        )

        results.append({
            "vendor": vendor_name,
            "sent": True,
            "mode": "link",
            "files": len(links),
        })

    return {
        "sent": True,
        "vendors_processed": len(vendors),
        "results": results,
    }