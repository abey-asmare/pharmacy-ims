"""
SettingsService — ODD Table 3.1.

    get(key): value
    get_windows(): list[int]
    update(key, value, actor)

SDD 2.4: "setting (configurable values such as warning windows,
consumption period, cover days, and reminder lead days)". Read by
inventory, notification, and the background jobs; changed only by a
Pharmacy Admin (SDD Table 3.3: /settings).

Values are validated per key so an Admin typing "sixty" for
consumption_days gets a 422 immediately, instead of the failure
surfacing days later inside a scheduled job that can't parse the value.
"""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import UserAccount
from app.auth.service import AuditService
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.models import Setting


# Keys the application recognises. Anything else raises, so a typo in a
# caller (get("warning_window") — missing 's') fails loudly during
# development rather than silently returning nothing.
ALLOWED_KEYS: frozenset[str] = frozenset({
    "warning_windows",            # FR-EXP-02 / FR-EXP-06
    "consumption_days",           # BR-03 / FR-ROR-02
    "cover_days",                 # BR-05 / FR-ROR-03
    "reminder_lead_days",         # BR-07 / FR-NTF-05
    "max_notification_attempts",  # FR-NTF-09
})


# --------------------------------------------------------------------- #
# Per-key validators: each takes the raw string from the API and either
# returns a normalised string (to store) or raises ValidationFailedError.
# --------------------------------------------------------------------- #
def _parse_warning_windows(raw: str) -> str:
    """Comma-separated positive ints, 1-3 of them, normalised to descending order."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValidationFailedError("warning_windows must contain at least one number.")
    if len(parts) > 3:
        raise ValidationFailedError("warning_windows may contain at most three numbers.")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        raise ValidationFailedError("warning_windows must be comma-separated integers.")
    if any(n < 1 or n > 365 for n in nums):
        raise ValidationFailedError("warning_windows values must be between 1 and 365 days.")
    # BR-02 describes the windows as 90, 60, 30 — descending. Sort here
    # so a value typed in any order is stored consistently.
    nums = sorted(set(nums), reverse=True)
    return ",".join(str(n) for n in nums)


def _parse_bounded_int(min_value: int, max_value: int, field: str) -> Callable[[str], str]:
    def _inner(raw: str) -> str:
        try:
            n = int(raw.strip())
        except (ValueError, AttributeError) as exc:
            raise ValidationFailedError(f"{field} must be an integer.") from exc
        if n < min_value or n > max_value:
            raise ValidationFailedError(
                f"{field} must be between {min_value} and {max_value}."
            )
        return str(n)

    return _inner


VALIDATORS: dict[str, Callable[[str], str]] = {
    "warning_windows":           _parse_warning_windows,
    "consumption_days":          _parse_bounded_int(1, 365, "consumption_days"),
    "cover_days":                _parse_bounded_int(1, 180, "cover_days"),
    "reminder_lead_days":        _parse_bounded_int(0, 30, "reminder_lead_days"),
    "max_notification_attempts": _parse_bounded_int(1, 10, "max_notification_attempts"),
}


class SettingsService:
    def __init__(self, db: Session):
        self.db = db
        # AuditService lives in app.auth.service because this repo keeps
        # audit inside the auth package (see ODD docstring there). That
        # makes this a small layering exception — core importing from
        # auth — which is acceptable given the current structure. If it
        # ever bites, move AuditService to app/core/audit_service.py and
        # update the imports; everything else stays the same.
        self.audit = AuditService(db)

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def get(self, key: str) -> str:
        """Return the raw value for a known, seeded setting key."""
        return self.get_row(key).value

    def get_row(self, key: str) -> Setting:
        """Return the Setting row for a key, or raise if unknown or unseeded."""
        self._require_known(key)
        row = self.db.execute(
            select(Setting).where(Setting.key == key)
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(
                f"Setting {key!r} has not been seeded. Run scripts/seed_settings.py."
            )
        return row

    def get_windows(self) -> list[int]:
        """Parsed warning windows, sorted descending (BR-02)."""
        raw = self.get("warning_windows")
        return sorted((int(x) for x in raw.split(",") if x.strip()), reverse=True)

    def get_all(self) -> list[Setting]:
        """Every setting, ordered by key, for the Admin screen (SDD Table 3.3)."""
        return list(
            self.db.execute(select(Setting).order_by(Setting.key)).scalars()
        )

    # ------------------------------------------------------------------ #
    # Update — Admin only, enforced at the router AND re-checked here
    # ------------------------------------------------------------------ #
    def update(self, key: str, value: str, actor: UserAccount) -> Setting:
        """Validate, normalise, persist, and audit one setting change.

        Runs in a single transaction: the value change and the audit entry
        succeed or fail together (SDD 2.6, NFR-06).
        """
        self._require_known(key)
        normalised = VALIDATORS[key](value)

        row = self.db.execute(
            select(Setting).where(Setting.key == key)
        ).scalar_one_or_none()

        old_value: str | None = None
        if row is None:
            # Admin is adding a key that was never seeded. Legitimate but
            # unusual; the audit trail records "<unset> -> new" so it's
            # visible later.
            row = Setting(key=key, value=normalised)
            self.db.add(row)
        else:
            old_value = row.value
            row.value = normalised
            # updated_at is handled by TimestampMixin's onupdate — no
            # manual assignment needed.

        self.db.flush()
        self.audit.record(
            actor,
            action="update_setting",
            entity_type="setting",
            entity_id=key,
            details=f"{old_value if old_value is not None else '<unset>'} -> {normalised}",
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _require_known(self, key: str) -> None:
        if key not in ALLOWED_KEYS:
            raise ValidationFailedError(
                f"Unknown setting key {key!r}. "
                f"Known keys: {', '.join(sorted(ALLOWED_KEYS))}."
            )