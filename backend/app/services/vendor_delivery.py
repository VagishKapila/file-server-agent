from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.file_delivery import prepare_files_for_vendor
from backend.app.services.email_sender import send_email


async def send_vendor_documents(
    *,
    project_request_id: int,
    vendor_email: str,
    db: AsyncSession,
    vendor_name: str = "Vendor",
) -> Dict:
    """
    Final delivery orchestrator.
    - Decides attach vs link
    - Sends email
    - Reusable for subs + materials
    """

    file_info = await prepare_files_for_vendor(
        project_request_id=project_request_id,
        db=db,
    )

    subject = "Project Documents & Scope Information"

    if file_info["mode"] == "none":
        body = f"""
        Hi {vendor_name},

        There are no files attached for this project yet.
        We will follow up shortly if anything is added.

        Thanks,
        Project Team
        """
        send_email(
            to_email=vendor_email,
            subject=subject,
            html_body=body,
            attachments=[],
        )

        return {"mode": "none", "sent": True}

    if file_info["mode"] == "attach":
        body = f"""
        Hi {vendor_name},

        Please find the project documents attached.
        Total size: {file_info.get("total_mb")} MB

        Thanks,
        Project Team
        """

        attachments = [f["stored_path"] for f in file_info["files"]]

        send_email(
            to_email=vendor_email,
            subject=subject,
            html_body=body,
            attachments=attachments,
        )

        return {
            "mode": "attach",
            "sent": True,
            "files": file_info["files"],
        }

    # mode == link
    links = [
        f["stored_path"] for f in file_info["files"]
    ]

    link_list = "<br>".join(links)

    body = f"""
    Hi {vendor_name},

    The project files are available at the links below:
    <br><br>
    {link_list}
    <br><br>
    Thanks,
    Project Team
    """

    send_email(
        to_email=vendor_email,
        subject=subject,
        html_body=body,
        attachments=[],
    )

    return {
        "mode": "link",
        "sent": True,
        "files": file_info["files"],
    }