from __future__ import annotations

import logging
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
)
from .ws_hub import hub
from . import db  # noqa: F401  # ensure sqlite init

logger = logging.getLogger("zhice.api")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
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
app.include_router(ws.router, prefix="/api")


@app.get("/api/health")
def health():
    from .db import get_conn
    status = {"api": "ok", "database": "ok"}
    try:
        conn = get_conn()
        conn.execute("SELECT 1")
        conn.close()
    except Exception:
        status["database"] = "error"
    overall = "ok" if all(v == "ok" for v in status.values()) else "degraded"
    return {"status": overall, "components": status}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    if settings.debug:
        detail = str(exc)
    else:
        detail = "服务内部错误，请稍后重试"
    return JSONResponse(status_code=500, content={"detail": detail})
