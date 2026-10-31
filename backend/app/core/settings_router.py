"""
/settings — SDD Table 3.3, UC-14. Admin only.

| Resource          | Operations   | Roles | Use case |
|-------------------|--------------|-------|----------|
| /settings         | List         | Admin | UC-14    |
| /settings/{key}   | View, update | Admin | UC-14    |
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.models import Role, UserAccount
from app.core.db import get_db
from app.core.deps import require_role
from app.core.settings_schemas import SettingResponse, SettingUpdateRequest
from app.core.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[SettingResponse])
def list_settings(
    db: Session = Depends(get_db),
    _: UserAccount = Depends(require_role(Role.PHARMACY_ADMIN)),
) -> list[SettingResponse]:
    """Every configurable setting and its current value (UC-14)."""
    rows = SettingsService(db).get_all()
    return [SettingResponse.model_validate(r) for r in rows]


@router.get("/{key}", response_model=SettingResponse)
def get_setting(
    key: str,
    db: Session = Depends(get_db),
    _: UserAccount = Depends(require_role(Role.PHARMACY_ADMIN)),
) -> SettingResponse:
    """One setting by key (UC-14)."""
    return SettingResponse.model_validate(SettingsService(db).get_row(key))


@router.patch("/{key}", response_model=SettingResponse)
def update_setting(
    key: str,
    body: SettingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(Role.PHARMACY_ADMIN)),
) -> SettingResponse:
    """Update one setting. Validated per key (UC-14, FR-EXP-06)."""
    setting = SettingsService(db).update(key, body.value, current_user)
    return SettingResponse.model_validate(setting)