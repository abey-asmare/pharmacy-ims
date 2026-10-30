from __future__ import annotations

import argparse

from app.auth.models import Role, UserAccount
from app.core.db import SessionLocal
from app.core.security import SecurityService


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()

    email = args.email.lower()
    db = SessionLocal()
    try:
        if db.query(UserAccount).filter_by(email=email).first():
            raise SystemExit(f"User already exists: {email}")
        db.add(UserAccount(
            full_name=args.name,
            email=email,
            password_hash=SecurityService.hash_password(args.password),
            role=Role.PHARMACY_ADMIN,
            is_active=True,
        ))
        db.commit()
        print(f"Admin created: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()