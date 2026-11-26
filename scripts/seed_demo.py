#!/usr/bin/env python3
"""Create the demo account used by the local (no-Supabase) mode.

    python scripts/seed_demo.py

Idempotent. The account is created already confirmed so it can be used to log in
straight away, while new sign-ups still go through the (now working) confirmation
link flow:

    email:    demo@wastewise.local
    password: waste1234

Only for LOCAL_MODE. It refuses to run against a Supabase deployment.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import get_settings           # noqa: E402
from app.database.local_store import LocalStore  # noqa: E402

DEMO_EMAIL = "demo@wastewise.local"
DEMO_PASSWORD = "waste1234"
DEMO_NAME = "Demo User"


def main() -> int:
    settings = get_settings()
    if not settings.local_mode:
        print("LOCAL_MODE is off: this script only seeds the local SQLite store.")
        print("Set LOCAL_MODE=1 in backend/.env (see docs/local-demo.md).")
        return 1
    store = LocalStore(settings.local_db_path, settings.local_storage_dir, settings.public_base_url)
    existing = store.get_user_by_email(DEMO_EMAIL)
    if existing:
        store.confirm_user(DEMO_EMAIL)
        store.update_password(existing["id"], DEMO_PASSWORD)
        print(f"demo account refreshed: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        return 0
    store.create_user(DEMO_EMAIL, DEMO_PASSWORD, DEMO_NAME, confirmed=True)
    print(f"demo account created:  {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print(f"  database: {settings.local_db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
