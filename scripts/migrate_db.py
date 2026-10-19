"""Apply repo/schema.sql then repo/roles.sql. Needs CHANGECTL_APP_PASSWORD."""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from clients.db import get_conn  # noqa: E402


def main() -> None:
    password = os.environ.get("CHANGECTL_APP_PASSWORD")
    if not password:
        sys.exit("CHANGECTL_APP_PASSWORD is not set; refusing to create the app role")
    if "'" in password:
        sys.exit("CHANGECTL_APP_PASSWORD must not contain a single quote")

    schema = (REPO_ROOT / "repo" / "schema.sql").read_text()
    roles = (REPO_ROOT / "repo" / "roles.sql").read_text().replace("__APP_PASSWORD__", password)

    conn = get_conn()
    try:
        conn.execute(schema)
        print("applied repo/schema.sql")
        conn.execute(roles)
        print("applied repo/roles.sql")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
