from __future__ import annotations

import collections
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .routes import (
    replay,
    intraday,
    sentiment,
    theme,
    stock,
    ai,
    strategy,
    chain,
    analysis,
    board_replay,
    top_traders,
    growth,
    value,
    advanced_strategy,
    etf,
    ws,
    auth,
    events,
    payment,
    style as style_route,
    dashboard,
    longhu,
    rotation,
    recommend,
    research,
    lab,
    watchlist,
    finance,
    news,
    admin,
)
from .ws_hub import hub
from . import db  # noqa: F401  # trigger engine lazy build + best-effort admin seed

logger = logging.getLogger("zhice.api")

_5xx_window: collections.deque[float] = collections.deque(maxlen=1000)
_5xx_lock = threading.Lock()


def get_5xx_count(window_seconds: int = 300) -> int:
    cutoff = time.time() - window_seconds
    with _5xx_lock:
        return sum(1 for ts in _5xx_window if ts >= cutoff)


def _reset_5xx_window_for_tests() -> None:
    with _5xx_lock:
        _5xx_window.clear()


# Startup validation has already run inside Settings.validate_required_secrets
# at config import time; reaching this line means the gate passed. Log the
# observable shape (debug flag + DATABASE_URL scheme) so operators can confirm
# without exposing any secret value.
logger.info(
    "启动校验通过：debug=%s, database_url scheme=%s",
    settings.debug,
    settings.database_url.split("://", 1)[0] if settings.database_url else "none",
)


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        if response.status_code >= 500:
            with _5xx_lock:
                _5xx_window.append(time.time())
        logger.info(
            "%s %s %d %.0fms",
            request.method, request.url.path, response.status_code, elapsed,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .scheduler import start_scheduler, stop_scheduler
    try:
        start_scheduler()
        await hub.start()
        yield
    finally:
        await hub.stop()
        stop_scheduler()
        from apps.ai.agents.llm_client import llm
        llm.close()


app = FastAPI(
    title="智策 API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(RequestLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(replay.router, prefix="/api/market", tags=["replay"])
app.include_router(intraday.router, prefix="/api/market", tags=["intraday"])
app.include_router(sentiment.router, prefix="/api/market", tags=["sentiment"])
app.include_router(theme.router, prefix="/api/theme", tags=["theme"])
app.include_router(stock.router, prefix="/api/stock", tags=["stock"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(strategy.router, prefix="/api/strategy", tags=["strategy"])
app.include_router(chain.router, prefix="/api/chain", tags=["chain"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(board_replay.router, prefix="/api/analysis", tags=["board-replay"])
app.include_router(top_traders.router, prefix="/api/analysis", tags=["top-traders"])
app.include_router(growth.router, prefix="/api/growth", tags=["growth"])
app.include_router(value.router, prefix="/api/value", tags=["value"])
app.include_router(advanced_strategy.router, prefix="/api/advanced-strategy", tags=["advanced-strategy"])
app.include_router(etf.router, prefix="/api/etf", tags=["etf"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(payment.router, prefix="/api/payment", tags=["payment"])
app.include_router(style_route.router, prefix="/api/style", tags=["style"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(longhu.router, prefix="/api/longhu", tags=["longhu"])
app.include_router(rotation.router, prefix="/api/rotation", tags=["rotation"])
app.include_router(recommend.router, prefix="/api/recommend", tags=["recommend"])
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(lab.router, prefix="/api/lab", tags=["lab"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(finance.router, prefix="/api/finance", tags=["finance"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(ws.router, prefix="/api")


@app.get("/api/health")
def health():
    """Surface API + DB liveness, the active DB scheme, and alembic revision.

    T03 (M001/S01) extended this from a binary "ok/degraded" to a structured
    response that reveals (a) whether the configured DB scheme is mysql or
    legacy sqlite — useful for catching mis-deploys — and (b) the alembic
    ``version_num`` of the running schema, which tells operators if a
    migration was applied without having to shell into the container.
    """
    from .db import get_engine

    components: dict[str, str] = {"api": "ok", "database": "ok"}
    db_scheme = (
        settings.database_url.split("://", 1)[0].lower() if settings.database_url else "none"
    )
    alembic_revision: str | None = None

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
            try:
                row = conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()
                if row is not None:
                    alembic_revision = row[0]
            except Exception:
                # alembic_version absent → migration hasn't run yet.
                alembic_revision = None
    except Exception:
        components["database"] = "error"

    overall = "ok" if all(v == "ok" for v in components.values()) else "degraded"
    return {
        "status": overall,
        "components": components,
        "db_scheme": db_scheme,
        "alembic_revision": alembic_revision,
        "five_xx_recent": get_5xx_count(),
    }


@app.get("/api/health/kpl")
def health_kpl():
    """KPL realtime/history dual probe state (M001/S03/T05).

    Public — no auth — by design: the business owner needs to spot a red light
    from the homepage without admin login. The response intentionally excludes
    cookie material; only ``status`` / ``last_ok_at`` / ``last_error`` /
    ``consecutive_fail`` per probe are exposed (see ``kpl_health.py``).
    """
    from .services.kpl_health import get_health_cache

    return get_health_cache()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    if settings.debug:
        detail = str(exc)
    else:
        detail = "服务内部错误，请稍后重试"
    return JSONResponse(status_code=500, content={"detail": detail})
