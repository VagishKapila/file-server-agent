from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def match_inbound_email(
    inbound_email_id: int,
    db: AsyncSession,
):
    """
    Attempt to associate inbound email with a project_request
    """

    result = await db.execute(
        text("SELECT * FROM inbound_emails WHERE id = :id"),
        {"id": inbound_email_id},
    )
    email = result.mappings().first()

    if not email:
        return None

    # ---- Strategy 1: reply+prj_<id>@domain ----
    to_email = email["to_email"] or ""
    if "prj_" in to_email:
        try:
            project_id = int(to_email.split("prj_")[1].split("@")[0])
            await db.execute(
                text("""
                    UPDATE inbound_emails
                    SET project_request_id = :pid, status = 'matched'
                    WHERE id = :id
                """),
                {"pid": project_id, "id": inbound_email_id},
            )
            await db.commit()
            return project_id
        except Exception:
            pass

    # ---- Strategy 2: message_id match ----
    result = await db.execute(
        text("""
            SELECT project_id FROM supplier_outreach
            WHERE message_id = :mid
        """),
        {"mid": email["message_id"]},
    )
    outreach = result.first()

    if outreach:
        await db.execute(
            text("""
                UPDATE inbound_emails
                SET project_request_id = :pid, status = 'matched'
                WHERE id = :id
            """),
            {"pid": outreach.project_id, "id": inbound_email_id},
        )
        await db.commit()
        return outreach.project_id

    # ---- No match ----
    await db.execute(
        text("""
            INSERT INTO inbound_email_unmatched
            (inbound_email_id, reason)
            VALUES (:id, 'no_project_match')
        """),
        {"id": inbound_email_id},
    )
    await db.commit()

    return None