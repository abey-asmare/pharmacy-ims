"""
core/models.py — Setting entity.

SDD 2.4: "setting (configurable values such as warning windows,
consumption period, cover days, and reminder lead days)". Read by
inventory, notification, and the background jobs; changed only by a
Pharmacy Admin (SDD Table 3.3: /settings). It lives in core/ because
there's no dedicated settings package in this repo and it's a shared,
foundational concern — same reasoning as db session and security.

Stored as simple key/value pairs so a new setting doesn't need a
migration; whoever builds SettingsService is responsible for parsing and
validating the value for the key it's asked for.
"""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin


class Setting(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)