# changectl

FastAPI + Postgres change-control service.

## Local dev

```bash
docker compose up -d
python3.13 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
CHANGECTL_TEST_DSN=postgresql://changectl:changectl@localhost:5434/changectl .venv/bin/pytest -q
```
