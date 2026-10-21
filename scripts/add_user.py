"""Insert a user (local dev seed): add_user.py EMAIL NAME [--role R] [--doc-manager].

Connects with the POSTGRES_* environment, like scripts/migrate_db.py.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clients.db import get_conn  # noqa: E402
from repo import users  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("email")
    p.add_argument("name")
    p.add_argument(
        "--role", default="engineering", choices=["engineering", "operations", "quality", "other"]
    )
    p.add_argument("--doc-manager", action="store_true")
    args = p.parse_args()

    conn = get_conn()
    try:
        row = users.insert(
            conn,
            email=args.email,
            name=args.name,
            role=args.role,
            is_doc_manager=args.doc_manager,
            invited_by=None,
        )
        conn.commit()
    finally:
        conn.close()
    print(f"added {row['email']} ({row['role']}, doc_manager={row['is_doc_manager']})")


if __name__ == "__main__":
    main()
