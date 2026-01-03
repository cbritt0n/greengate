import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import settings
from app.routers import chat
from app.services.metrics_service import energy_ledger
from app.services.proxy_service import proxy_service
from app.services.rate_limiter import configure_rate_limiter
from app.services.tracing import configure_tracing, shutdown_tracing

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("greengate")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_rate_limiter(settings.RATE_LIMIT_PER_MINUTE)
    configure_tracing(app)
    await energy_ledger.initialize()
    await proxy_service.initialize()
    logger.info(
        "Starting %s in %s mode (rate limit: %s req/min)",
        settings.PROJECT_NAME,
        settings.ENVIRONMENT,
        settings.RATE_LIMIT_PER_MINUTE,
    )
    yield
    await proxy_service.close()
    shutdown_tracing()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="An energy-aware AI Gateway/Proxy.",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(chat.router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


@app.get("/")
async def root():
    stats = await energy_ledger.snapshot()
    return {
        "message": "GreenGate is running",
        "environment": settings.ENVIRONMENT,
        "energy_spent_joules": stats["energy_spent"],
        "energy_saved_joules": stats["energy_saved"],
        "requests_served": stats["requests"],
    }


@app.get("/healthz")
async def healthcheck():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    if not settings.PROMETHEUS_METRICS_ENABLED:
        return Response(status_code=204)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
