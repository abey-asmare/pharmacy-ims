"""
Request dependencies (ODD 2: "app.core — ... request dependencies
(current user, role check)").

Every protected route declares which roles may use it via Depends on
require_role(...); the check happens before any service runs
(SDD 2.5 — "the API layer refuses other requests before any service
runs").
"""
from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import SecurityService
from app.core.db import get_db
from app.auth.models import Role, UserAccount

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> UserAccount:
    """Decodes the bearer token and loads the matching, active user."""
    if credentials is None:
        raise AuthenticationError("Missing authentication token.")

    payload = SecurityService.decode_token(credentials.credentials)

    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError as exc:
        raise AuthenticationError("Invalid authentication token.") from exc

    user = db.get(UserAccount, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid session. Please log in again.")

    return user


def require_role(*allowed_roles: Role) -> Callable[[UserAccount], UserAccount]:
    """Dependency factory: Depends(require_role(Role.PHARMACY_ADMIN)).

    Pharmacy Admin is allowed to do everything Pharmacy Staff can do
    (SRS 3.3.1), so a route guarded for Staff also admits Admin.
    """

    def _checker(user: UserAccount = Depends(get_current_user)) -> UserAccount:
        effective_allowed = set(allowed_roles)
        if Role.PHARMACY_STAFF in effective_allowed:
            effective_allowed.add(Role.PHARMACY_ADMIN)
        if user.role not in effective_allowed:
            raise PermissionDeniedError(
                f"This action requires one of: {', '.join(r.value for r in allowed_roles)}."
            )
        return user

    return _checker