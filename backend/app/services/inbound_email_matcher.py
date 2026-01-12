from app.db import database


async def match_inbound_email(inbound_email_id: int):
    """
    Attempt to associate inbound email with a project_request
    """

    email = await database.fetch_one(
        "SELECT * FROM inbound_emails WHERE id = :id",
        {"id": inbound_email_id},
    )

    if not email:
        return None

    # ---- Strategy 1: reply+prj_<id>@domain ----
    to_email = email["to_email"] or ""
    if "prj_" in to_email:
        try:
            project_id = int(to_email.split("prj_")[1].split("@")[0])
            await database.execute(
                """
                UPDATE inbound_emails
                SET project_request_id = :pid, status = 'matched'
                WHERE id = :id
                """,
                {"pid": project_id, "id": inbound_email_id},
            )
            return project_id
        except Exception:
            pass

    # ---- Strategy 2: message_id match ----
    outreach = await database.fetch_one(
        """
        SELECT project_id FROM supplier_outreach
        WHERE message_id = :mid
        """,
        {"mid": email["message_id"]},
    )

    if outreach:
        await database.execute(
            """
            UPDATE inbound_emails
            SET project_request_id = :pid, status = 'matched'
            WHERE id = :id
            """,
            {"pid": outreach["project_id"], "id": inbound_email_id},
        )
        return outreach["project_id"]

    # ---- No match ----
    await database.execute(
        """
        INSERT INTO inbound_email_unmatched
        (inbound_email_id, reason)
        VALUES (:id, 'no_project_match')
        """,
        {"id": inbound_email_id},
    )

    return None
