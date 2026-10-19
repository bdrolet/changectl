"""Smoke the API: health, me, create a change, upload an xlsx, read it back, list documents.

Without --token it relies on the dev bypass (CHANGECTL_DEV_USER_EMAIL on the server).
"""

import argparse
import io
import sys

import httpx
from openpyxl import Workbook


def make_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["item", "qty"])
    ws.append(["widget", 3])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:8080")
    p.add_argument("--token", help="Google ID token; omit to use the server's dev bypass")
    args = p.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    client = httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=30)

    def step(label: str, resp: httpx.Response) -> dict | list:
        print(f"{label}: {resp.status_code}")
        if not resp.is_success:
            print(resp.text)
            sys.exit(1)
        return resp.json()

    step("GET /health", client.get("/health"))
    step("GET /me", client.get("/me"))
    change = step(
        "POST /changes",
        client.post(
            "/changes",
            json={
                "title": "Smoke test change",
                "description": "Created by scripts/test-api-local.py",
                "reason": "Verify the deployment",
                "justification": "Smoke test",
            },
        ),
    )
    assert isinstance(change, dict)
    cid = change["id"]
    step(
        f"POST /changes/{cid}/revisions",
        client.post(
            f"/changes/{cid}/revisions",
            data={"title": "Smoke document"},
            files={
                "file": (
                    "smoke.xlsx",
                    make_xlsx(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        ),
    )
    detail = step(f"GET /changes/{cid}", client.get(f"/changes/{cid}"))
    assert isinstance(detail, dict)
    docs = step("GET /documents", client.get("/documents"))
    print(f"documents listed: {len(docs)}")
    print(f"change number: {detail['number']}")


if __name__ == "__main__":
    main()
