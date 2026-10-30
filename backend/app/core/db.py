"""
Database base class, engine, and session (Sprint Plan §4: "core/ —
config, db session, security, role-guard").

Conventions (per the ODD's naming table): singular snake_case table
names; primary key named `id`; foreign keys named `<entity>_id`.
Synchronous sessions throughout (ODD 1.2 trade-off table).
"""
import uuid
from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Shared declarative base. Every package's models.py imports this."""
    pass


class UUIDPKMixin:
    """Gives an entity a UUID primary key named `id`."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """created_at / updated_at, stored in UTC."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()