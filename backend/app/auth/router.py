"""
/auth and /users — SDD Table 3.3.

| Resource | Operations                               | Roles | Use cases |
|----------|-------------------------------------------|-------|-----------|
| /auth    | Log in, log out                            | All   | UC-01     |
| /users   | List, create, change role or status        | Admin | UC-02     |
"""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, require_role
from app.core.db import get_db
from app.auth.models import Role, UserAccount
from app.auth.schemas import (
    LoginRequest,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
)
from app.auth.service import AuthService

from sqlalchemy import select
from app.auth.schemas import AuditLogResponse     
from app.auth.service import AuditService          

settings = get_settings()

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


# --------------------------------------------------------------------- #
# /auth — UC-01
# --------------------------------------------------------------------- #
@auth_router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token = AuthService(db).authenticate(body.email, body.password)
    return TokenResponse(access_token=token, expires_in_minutes=settings.JWT_EXPIRE_MINUTES)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_: UserAccount = Depends(get_current_user)) -> None:
    """Stateless token (SDD 2.1/ODD 1.2): the server holds no session to
    end. The client discards the token; this route exists so the client
    has a single, auditable 'log out' call and so a blocklist can be
    added later without changing the interface."""
    return None


@auth_router.get("/me", response_model=UserResponse)
def read_me(current_user: UserAccount = Depends(get_current_user)) -> UserAccount:
    return current_user


# --------------------------------------------------------------------- #
# /users — UC-02, Admin only
# --------------------------------------------------------------------- #
@users_router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(Role.PHARMACY_ADMIN)),
) -> list[UserAccount]:
    return AuthService(db).list_users(current_user)


@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(Role.PHARMACY_ADMIN)),
) -> UserAccount:
    return AuthService(db).create_user(body, current_user)


@users_router.patch("/{user_id}/role", response_model=UserResponse)
def change_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(Role.PHARMACY_ADMIN)),
) -> UserAccount:
    return AuthService(db).change_role(user_id, body.role, current_user)


@users_router.patch("/{user_id}/status", response_model=UserResponse)
def change_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(Role.PHARMACY_ADMIN)),
) -> UserAccount:
    return AuthService(db).set_active(user_id, body.is_active, current_user)


# --------------------------------------------------------------------- #
# /audit — UC-19, FR-AUT-06, Admin only
# --------------------------------------------------------------------- #
audit_router = APIRouter(prefix="/audit", tags=["audit"])


@audit_router.get("", response_model=list[AuditLogResponse])
def list_audit_log(
    entity_type: str | None = None,
    user_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(Role.PHARMACY_ADMIN)),
) -> list[AuditLogResponse]:
    """List audit entries, newest first. Admin only (FR-AUT-06).

    Optional filters match the ones on AuditService.list_entries — an
    Admin investigating a stock discrepancy can narrow to a single
    entity_type ("batch", "purchase_order") or a single actor.
    """
    entries = AuditService(db).list_entries(
        entity_type=entity_type,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    # Enrich with actor email — one extra query, not N+1, because we only
    # look up the distinct set of user_ids that appear in this page.
    user_ids = {e.user_id for e in entries if e.user_id is not None}
    actor_emails: dict[uuid.UUID, str] = {}
    if user_ids:
        rows = db.execute(
            select(UserAccount.id, UserAccount.email).where(UserAccount.id.in_(user_ids))
        ).all()
        actor_emails = {row.id: row.email for row in rows}

    return [
        AuditLogResponse(
            id=e.id,
            user_id=e.user_id,
            actor_email=actor_emails.get(e.user_id) if e.user_id else None,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            details=e.details,
            created_at=e.created_at,
        )
        for e in entries
    ]