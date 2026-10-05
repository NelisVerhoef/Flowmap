"""Seed "existing production data" with raw SQL, independent of the app's code.

Run against a database migrated at the base revision, before deploying a change on top of it.
Users get argon2 hashes made here with pwdlib directly, as the base app would have made them.

    DATABASE_URL=postgresql://... python seed.py
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

ARGON2 = PasswordHash((Argon2Hasher(),))


def uid(name):
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"{name}.flowmap-bench")


# email -> (password, is_superuser, is_active)
USERS = {
    "admin@example.com": ("changethis", True, True),
    "alice@example.com": ("alice-pass-1", False, True),
    "bob@example.com": ("bob-pass-12", False, True),
    "carol@example.com": ("carol-pass-1", False, False),   # deactivated
    "dan@example.com": ("dan-pass-123", False, True),      # "dan@example.co" is a prefix of this
    "eve@example.com": ("eve-pass-123", False, True),      # gets deleted by the admin test
    **{f"user{i:02}@example.com": ("filler-pass-1", False, True) for i in range(15)},
}
USER_ID = {email: uid(email) for email in USERS}

LONG_TITLE = "Quarterly planning notes " + "x" * 175   # 200 chars: valid at base (max 255)
# item name -> (owner email, title)
ITEMS = {
    "alice-1": ("alice@example.com", "Alice's first item"),
    "alice-long": ("alice@example.com", LONG_TITLE),
    "bob-1": ("bob@example.com", "Bob's item"),
    "eve-1": ("eve@example.com", "Eve's item one"),
    "eve-2": ("eve@example.com", "Eve's item two"),
}
ITEM_ID = {name: uid(f"item-{name}") for name in ITEMS}


def dsn():
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def main():
    now = datetime.now(UTC)
    with psycopg.connect(dsn()) as conn:
        for i, (email, (password, superuser, active)) in enumerate(USERS.items()):
            conn.execute(
                'INSERT INTO "user" (id, email, is_active, is_superuser, full_name, hashed_password, created_at)'
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (USER_ID[email], email, active, superuser, email.split("@")[0].title(),
                 ARGON2.hash(password), now - timedelta(days=30, minutes=i)))
        for i, (name, (owner, title)) in enumerate(ITEMS.items()):
            conn.execute(
                "INSERT INTO item (id, title, description, owner_id, created_at) VALUES (%s, %s, %s, %s, %s)",
                (ITEM_ID[name], title, f"seeded {name}", USER_ID[owner], now - timedelta(days=20, minutes=i)))
    print(f"seeded {len(USERS)} users, {len(ITEMS)} items")


if __name__ == "__main__":
    main()
