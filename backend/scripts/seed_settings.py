"""
Seed the setting table with the project's documented defaults.

Idempotent — safe to run after every ``alembic upgrade head``. Values
are only inserted if the key isn't already present, so an Admin's
edited value is never overwritten by a redeploy.

Defaults trace to the SRS:
    warning_windows             FR-EXP-02   (90, 60, 30)
    consumption_days            BR-03       (N = 30)
    cover_days                  BR-05       (14)
    reminder_lead_days          BR-07       (5)
    max_notification_attempts   FR-NTF-09   (a limited number — 3)
"""
from app.core.db import SessionLocal
from app.core.models import Setting

DEFAULTS = [
    ("warning_windows", "90,60,30",
     "Expiry warning windows in days, comma-separated (FR-EXP-02)"),
    ("consumption_days", "30",
     "Window for average daily consumption, in days (BR-03)"),
    ("cover_days", "14",
     "Days of expected sales a reorder should cover (BR-05)"),
    ("reminder_lead_days", "5",
     "Days before the run-out date to send a refill reminder (BR-07)"),
    ("max_notification_attempts", "3",
     "Retry limit for failed notification deliveries (FR-NTF-09)"),
]


def main() -> None:
    db = SessionLocal()
    try:
        existing = {s.key for s in db.query(Setting).all()}
        for key, value, description in DEFAULTS:
            if key in existing:
                print(f"  skip   {key} (already set)")
                continue
            db.add(Setting(key=key, value=value, description=description))
            print(f"  insert {key} = {value!r}")
        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()