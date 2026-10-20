"""Apply repo/schema.sql then repo/roles.sql.

Terraform owns the changectl_app password in the deployed project, so there
the role already exists and CHANGECTL_APP_PASSWORD is not needed: roles.sql
never changes an existing role's password. Locally (compose) the role does not
exist yet, so CHANGECTL_APP_PASSWORD must be set (to `app`) to create it.
"""

import os
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from clients.db import get_conn  # noqa: E402


def main() -> None:
    password = os.environ.get("CHANGECTL_APP_PASSWORD")
    if password and "'" in password:
        sys.exit("CHANGECTL_APP_PASSWORD must not contain a single quote")

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'changectl_app') AS e"
        ).fetchone()
        role_exists = bool(row["e"])
        if role_exists:
            print("changectl_app exists; leaving its password alone (Terraform owns it)")
        elif password:
            print("changectl_app does not exist; creating it with CHANGECTL_APP_PASSWORD")
        else:
            sys.exit("changectl_app does not exist and CHANGECTL_APP_PASSWORD is not set")
        # Unused when the role exists: roles.sql only reads it on CREATE ROLE.
        substitute = password or secrets.token_urlsafe(32)
        schema = (REPO_ROOT / "repo" / "schema.sql").read_text()
        roles = (REPO_ROOT / "repo" / "roles.sql").read_text()
        conn.execute(schema)
        print("applied repo/schema.sql")
        conn.execute(roles.replace("__APP_PASSWORD__", substitute))
        print("applied repo/roles.sql")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
