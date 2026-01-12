from flask import Blueprint, request
from db import db

sendgrid_inbound = Blueprint("sendgrid_inbound", __name__)

@sendgrid_inbound.route("/sendgrid/inbound", methods=["POST"])
def inbound_email():
    # SendGrid sends multipart data
    headers = request.form.get("headers", "")
    subject = request.form.get("subject", "")
    from_email = request.form.get("from", "")
    body = request.form.get("text", "") or request.form.get("html", "")

    # Match by SendGrid Message-ID
    outreach = db.fetch_one("""
        SELECT id
        FROM supplier_outreach
        WHERE %s LIKE '%' || message_id || '%'
        LIMIT 1
    """, (headers,))

    if not outreach:
        return {"status": "ignored"}, 200

    db.execute("""
        INSERT INTO supplier_responses
        (supplier_outreach_id, raw_message)
        VALUES (%s, %s)
    """, (outreach["id"], body))

    db.execute("""
        UPDATE supplier_outreach
        SET status = 'replied'
        WHERE id = %s
    """, (outreach["id"],))

    return {"status": "ok"}, 200
