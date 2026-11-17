"""Assets and CMDB API router."""
from fastapi import APIRouter, Depends
from backend.database import SessionLocal
from backend.api.auth import require_roles
from backend.models import Asset, AssetAssignment, RoleEnum, User

router = APIRouter(
    prefix="/assets",
    tags=["assets"],
    dependencies=[Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator))],
)

@router.get("/")
def list_assets():
    db = SessionLocal()
    try:
        assets = db.query(Asset).all()
        output = []
        for a in assets:
            assignment = db.query(AssetAssignment).filter(AssetAssignment.asset_id == a.id).first()
            assigned_user = db.query(User).filter(User.id == assignment.user_id).first() if assignment else None
            output.append({
                "id": a.id,
                "serial_number": a.serial_number,
                "type": a.type,
                "model": a.model or "Standard Workstation",
                "assigned_to": assigned_user.email if assigned_user else "Unassigned",
                "status": "In Service" if assignment else "Available",
            })
        return output
    finally:
        db.close()

