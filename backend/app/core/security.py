"""
SecurityService — ODD Table 3.1.

    hash_password(password): str
    verify_password(password, hash): bool
    create_token(user): str
    decode_token(token): TokenPayload

Passwords are salted bcrypt hashes. Tokens are signed JWTs with a short
life (SDD 2.5 / ODD 1.2 "stateless token" trade-off): the API keeps no
session state, so any instance can serve any request.

bcrypt is used directly rather than through passlib — passlib 1.7.4
(last release 2020) reads ``bcrypt.__about__.__version__``, which bcrypt
removed in 4.1.0, so the combination raises AttributeError on the very
first hash with bcrypt 5.x. Using bcrypt directly removes an unmaintained
dependency and satisfies FR-AUT-02 ("salted hashes made with a recognised
password-hashing algorithm") on its own.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError


class TokenPayload(BaseModel):
    """Decoded, validated contents of an access token."""

    sub: str  # user id, as a string
    role: str
    exp: int


class SecurityService:
    """Static/stateless security helpers — no DB access, no side effects."""

    # ------------------------------------------------------------------ #
    # Passwords — FR-AUT-02 / SDD Table 2.7
    # ------------------------------------------------------------------ #
    @staticmethod
    def hash_password(password: str) -> str:
        """Return a salted bcrypt hash of ``password``.

        bcrypt encodes the salt inside the hash string itself, so no
        separate salt column is needed. The default work factor (12) is
        what ``bcrypt.gensalt()`` returns; it is intentionally left at the
        library default rather than tuned, because the target machine is
        an ordinary container host and login latency must stay within
        NFR-02.
        """
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Constant-time comparison of ``password`` against a bcrypt hash.

        Returns False (rather than raising) if ``password_hash`` is not a
        valid bcrypt hash — a corrupt or legacy row should produce a
        normal 401 from AuthService, not a 500. ``bcrypt.checkpw`` itself
        is constant-time over the hash and the input, so a wrong password
        does not leak how many leading characters matched.
        """
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False

    # ------------------------------------------------------------------ #
    # Tokens — SDD 2.5 / NFR-08
    # ------------------------------------------------------------------ #
    @staticmethod
    def create_token(user_id: UUID, role: str) -> str:
        """Sign a short-lived JWT carrying the user id and role.

        The token is stateless (ODD 1.2 "stateless token" trade-off): no
        server-side session is stored, so any API instance can validate it.
        ``role`` is embedded to avoid a DB round-trip on every request for
        the role check; ``get_current_user`` in deps.py still reloads the
        user row so a role change or deactivation takes effect immediately
        (SRS FR-AUT-03, SDD 2.5).
        """
        settings = get_settings()
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> TokenPayload:
        """Validate the signature and expiry, and return the payload.

        Every failure mode (expired, wrong signature, malformed) is raised
        as AuthenticationError so the single handler in main.py can map it
        to 401 without leaking which failure it was — same reasoning as
        the generic "Incorrect email or password" message in AuthService
        (SDD 2.7).
        """
        settings = get_settings()
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Session expired. Please log in again.") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Invalid authentication token.") from exc
        return TokenPayload(**payload)