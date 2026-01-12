from app.db import database


async def create_material_bid_from_email(inbound_email_id: int):
    """
    Convert a matched inbound email into a material bid
    """

    email = await database.fetch_one(
        """
        SELECT *
        FROM inbound_emails
        WHERE id = :id
          AND project_request_id IS NOT NULL
        """,
        {"id": inbound_email_id},
    )

    if not email:
        return None

    # Avoid duplicate bids
    existing = await database.fetch_one(
        """
        SELECT id FROM material_bids
        WHERE inbound_email_id = :id
        """,
        {"id": inbound_email_id},
    )

    if existing:
        return existing["id"]

    bid_id = await database.execute(
        """
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
        """,
        {
            "material_request_id": email["material_request_id"],
            "vendor_email": email["from_email"],
            "inbound_email_id": inbound_email_id,
            "raw_message": email["raw_text"] or email["raw_html"],
        },
    )

    # Mark inbound email as processed
    await database.execute(
        """
        UPDATE inbound_emails
        SET status = 'processed'
        WHERE id = :id
        """,
        {"id": inbound_email_id},
    )

    return bid_id
