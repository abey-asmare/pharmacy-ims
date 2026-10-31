"""
auth/service.py — AuditService and AuthService.

Both live here because this repo keeps audit logging inside the auth
package rather than as its own (Sprint Plan §4: "auth/ — login, users,
audit log").

AuditService (ODD Table 3.1):
    record(user, action, entity_ref, details)
    list_entries(filters): list[AuditLog]

AuthService (ODD Table 3.1):
    authenticate(email, password): str
    create_user(data, actor): UserAccount
    change_role(user_id, role, actor)
    set_active(user_id, active, actor)
    list_users(): list
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import AuditLog, Role, UserAccount
from app.auth.schemas import UserCreateRequest
from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.security import SecurityService

settings = get_settings()


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        user: UserAccount | None,
        action: str,
        entity_type: str,
        entity_id: str,
        details: str | None = None,
    ) -> AuditLog:
        """Adds the audit row to the current session. Does NOT commit —
        the caller's service commits once, as part of its own transaction
        (SDD 2.6: "one database transaction per use case")."""
        entry = AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=details,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_entries(
        self,
        *,
        entity_type: str | None = None,
        user_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        stmt = stmt.limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars().all())


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    # ---------------------------------------------------------------- #
    # Login
    # ---------------------------------------------------------------- #
    def authenticate(self, email: str, password: str) -> str:
        """Validate credentials and return a signed access token.

        SDD 2.7 / Table 2.7: passwords stored only as salted hashes, and a
        limit on repeated failed log-ins. SDD 2.6 / Table 2.8: the account
        must exist and be active. SRS §3.2.1: failed log-in attempts are
        recorded.
        """
        user = self.db.execute(
            select(UserAccount).where(UserAccount.email == email.lower())
        ).scalar_one_or_none()

        # Same generic message whether the email doesn't exist or the
        # password is wrong — don't leak which one it was (SDD 2.7).
        generic_error = AuthenticationError("Incorrect email or password.")

        if user is None:
            # SRS §3.2.1: record the failure even when the email is unknown.
            # user_id stays NULL; entity_id carries the attempted email so an
            # Admin can spot enumeration attempts against one address.
            self.audit.record(
                None,
                action="login_failed_unknown_email",
                entity_type="auth",
                entity_id=email.lower(),
            )
            self.db.commit()
            raise generic_error

        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise AuthenticationError(
                "This account is temporarily locked after repeated failed sign-ins. "
                "Try again later or ask a Pharmacy Admin to unlock it."
            )

        if not user.is_active:
            raise AuthenticationError("This account has been deactivated.")

        if not SecurityService.verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.LOCKOUT_MINUTES
                )
            # SRS §3.2.1 / FR-AUT-05: record the failure against the real user.
            self.audit.record(
                user,
                action="login_failed",
                entity_type="user_account",
                entity_id=str(user.id),
                details=f"attempt {user.failed_login_attempts}",
            )
            self.db.commit()
            raise generic_error

        # Success: reset the failed-attempt counter and issue a token.
        user.failed_login_attempts = 0
        user.locked_until = None
        self.audit.record(
            user,
            action="login",
            entity_type="user_account",
            entity_id=str(user.id),
        )
        self.db.commit()

        return SecurityService.create_token(user.id, user.role.value)

    # ---------------------------------------------------------------- #
    # User management — Admin only (enforced by the router's role-guard;
    # the service also re-checks, since it's the actual source of truth)
    # ---------------------------------------------------------------- #
    def create_user(self, data: UserCreateRequest, actor: UserAccount) -> UserAccount:
        self._require_admin(actor)

        existing = self.db.execute(
            select(UserAccount).where(UserAccount.email == data.email.lower())
        ).scalar_one_or_none()
        if existing:
            raise ValidationFailedError("A user with this email already exists.")

        user = UserAccount(
            full_name=data.full_name,
            email=data.email.lower(),
            password_hash=SecurityService.hash_password(data.password),
            role=data.role,
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()
        self.audit.record(
            actor, action="create_user", entity_type="user_account", entity_id=str(user.id)
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def change_role(self, user_id: uuid.UUID, role: Role, actor: UserAccount) -> UserAccount:
        self._require_admin(actor)
        user = self._get_user_or_404(user_id)
        previous_role = user.role.value
        user.role = role
        self.audit.record(
            actor,
            action="change_role",
            entity_type="user_account",
            entity_id=str(user.id),
            details=f"{previous_role} -> {role.value}",
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_active(self, user_id: uuid.UUID, active: bool, actor: UserAccount) -> UserAccount:
        self._require_admin(actor)
        user = self._get_user_or_404(user_id)
        if user.id == actor.id and not active:
            raise ValidationFailedError("You cannot deactivate your own account.")
        user.is_active = active
        self.audit.record(
            actor,
            action="set_active",
            entity_type="user_account",
            entity_id=str(user.id),
            details=str(active),
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def list_users(self, actor: UserAccount) -> list[UserAccount]:
        self._require_admin(actor)
        return list(self.db.execute(select(UserAccount).order_by(UserAccount.created_at)).scalars())

    # ---------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------- #
    def _require_admin(self, actor: UserAccount) -> None:
        if actor.role != Role.PHARMACY_ADMIN:
            raise PermissionDeniedError("Only a Pharmacy Admin may manage users.")

    def _get_user_or_404(self, user_id: uuid.UUID) -> UserAccount:
        user = self.db.get(UserAccount, user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user