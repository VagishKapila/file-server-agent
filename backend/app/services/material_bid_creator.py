from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_material_bid_from_email(
    inbound_email_id: int,
    db: AsyncSession,
):
    """
    Convert a matched inbound email into a material bid.
    Auto-creates material_request if missing.
    """

    # 1️⃣ Fetch inbound email (must be matched to a project)
    result = await db.execute(
        text("""
            SELECT *
            FROM inbound_emails
            WHERE id = :id
              AND project_request_id IS NOT NULL
        """),
        {"id": inbound_email_id},
    )
    email = result.mappings().first()

    if not email:
        return None

    project_id = email["project_request_id"]
    material_request_id = email.get("material_request_id")

    # 2️⃣ Ensure material_request exists
    if not material_request_id:
        result = await db.execute(
            text("""
                INSERT INTO material_requests
                (project_request_id, source, status)
                VALUES (:project_id, 'email_reply', 'open')
                RETURNING id
            """),
            {"project_id": project_id},
        )
        material_request_id = result.scalar_one()

        # Backfill inbound email
        await db.execute(
            text("""
                UPDATE inbound_emails
                SET material_request_id = :mrid
                WHERE id = :id
            """),
            {"mrid": material_request_id, "id": inbound_email_id},
        )

    # 3️⃣ Prevent duplicate bids
    result = await db.execute(
        text("""
            SELECT id
            FROM material_bids
            WHERE inbound_email_id = :id
        """),
        {"id": inbound_email_id},
    )
    existing = result.mappings().first()

    if existing:
        return existing["id"]

    # 4️⃣ Create material bid
    result = await db.execute(
        text("""
            INSERT INTO material_bids
            (
                material_request_id,
                vendor_email,
                inbound_email_id,
                raw_message,
                status
            )
            VALUES
            (
                :material_request_id,
                :vendor_email,
                :inbound_email_id,
                :raw_message,
                'received'
            )
            RETURNING id
        """),
        {
            "material_request_id": material_request_id,
            "vendor_email": email["from_email"],
            "inbound_email_id": inbound_email_id,
            "raw_message": email["raw_text"] or email["raw_html"],
        },
    )

    bid_id = result.scalar_one()

    # 5️⃣ Mark inbound email as processed
    await db.execute(
        text("""
            UPDATE inbound_emails
            SET status = 'processed'
            WHERE id = :id
        """),
        {"id": inbound_email_id},
    )

    await db.commit()
    return bid_id
