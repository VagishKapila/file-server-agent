from backend.app.db import get_db
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.models.materials import (
    MaterialVendor,
    MaterialOutreach,
    MaterialQuote,
)

router = APIRouter(prefix="/material-requests", tags=["Material Requests"])

@router.post("/")
def save_material_response(
    project_request_id: str,
    vendor_name: str,
    material_category: str,
    price: float | None = None,
    currency: str | None = None,
    lead_time_days: int | None = None,
    email: str | None = None,
    phone: str | None = None,
    db: Session = Depends(get_db),
):
    vendor = MaterialVendor(
        company_name=vendor_name,
        material_category=material_category
    )
    db.add(vendor)
    db.flush()

    outreach = MaterialOutreach(
        project_request_id=project_request_id,
        vendor_id=vendor.id,
        status="quoted"
    )
    db.add(outreach)
    db.flush()

    if price:
        db.add(MaterialQuote(
            outreach_id=outreach.id,
            price=price,
            currency=currency,
            lead_time_days=lead_time_days
        ))

    if email or phone:
        db.add(Contact(
            owner_type="material",
            owner_id=vendor.id,
            email=email,
            phone=phone,
            source="call"
        ))

    db.commit()

    return {
        "vendor_id": vendor.id,
        "outreach_id": outreach.id
    }
