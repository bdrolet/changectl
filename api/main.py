import logging

# force=True: the uvicorn runtime configures the root logger first, which would
# make basicConfig a no-op and drop app-code logs from Cloud Logging.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True)

import os

from fastapi import FastAPI, Request

import clients.otel as otel
from api import errors

otel.setup_telemetry(os.environ.get("K_SERVICE", "changectl-api-local"))

app = FastAPI(title="changectl-api")
errors.install(app)


@app.middleware("http")
async def request_metrics(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        route = getattr(request.scope.get("route"), "path", None) or "unmatched"
        otel.api_requests.add(1, {"route": route, "status": "500"})
        otel.flush()
        raise
    # scope["route"] is the matched route template (bounded cardinality), only
    # set after routing; unmatched paths label "unmatched", not the raw URL.
    route = getattr(request.scope.get("route"), "path", None) or "unmatched"
    otel.api_requests.add(1, {"route": route, "status": str(response.status_code)})
    otel.flush()
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


from api.routers import me  # noqa: E402

app.include_router(me.router)
