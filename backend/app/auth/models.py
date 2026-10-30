"""
auth — UserAccount entity.

SDD Table 2.5: AUT module owns user_account, audit_log.
SRS 3.3.1 / Table 3.1: roles are Pharmacy Admin, Pharmacy Staff, Clinic
Staff (Patient is a notification recipient, not a login role — patients
reach the system only through the public, unauthenticated reminder link,
SDD Table 3.3 "/reminders/{token}").
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin


class Role(str, enum.Enum):
    PHARMACY_ADMIN = "pharmacy_admin"
    PHARMACY_STAFF = "pharmacy_staff"
    CLINIC_STAFF = "clinic_staff"


class UserAccount(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "user_account"

    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # SDD 2.7: "limit on repeated failed log-ins" — simple lockout counter.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserAccount {self.email} ({self.role.value})>"


class AuditLog(UUIDPKMixin, Base):
    """
    SDD 2.4 / Table 2.6: "Audit and movement tables are written only by
    the services; the API offers no change or delete." This table has no
    update or delete path anywhere in the application — only
    AuditService.record() (service.py) inserts rows.
    """

    __tablename__ = "audit_log"

    # Nullable: a small number of system/job-triggered entries may have no
    # human actor (e.g. a scheduled job). Everything else always sets it.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Append-only: created_at only, no updated_at.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )