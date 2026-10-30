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