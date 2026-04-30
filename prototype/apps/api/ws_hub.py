from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import WebSocket

from packages.connectors.kpl.client import KplClient
from .config import settings

logger = logging.getLogger(__name__)

BROADCAST_INTERVAL = 3


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _payload(trade_date: str, data: list[dict], source: str = "kpl") -> dict:
    return {
        "trade_date": trade_date,
        "updated_at": _now_text(),
        "count": len(data),
        "data": data,
        "source": source,
        "data_status": "ok" if data else "empty",
        "mock": False,
    }


def _fetch_market_data() -> dict:
    trade_date = datetime.now().strftime("%Y-%m-%d")
    kpl = KplClient(
        user_id=settings.kpl_user_id,
        token=settings.kpl_token,
        device_id=settings.kpl_device_id,
        version=settings.kpl_version,
    )
    try:
        limit_up = kpl.get_limit_up(trade_date)
        broken = kpl.get_broken(trade_date)
        hot = kpl.get_hot_stocks(trade_date)
        try:
            anomaly = kpl.get_market_anomaly(trade_date)
        except Exception:
            anomaly = []
        return {
            "trade_date": trade_date,
            "updated_at": _now_text(),
            "source": "kpl",
            "data_status": "ok" if limit_up or broken or hot or anomaly else "empty",
            "mock": False,
            "limit_up": _payload(trade_date, limit_up),
            "broken": _payload(trade_date, broken),
            "hot": _payload(trade_date, hot),
            "anomaly": _payload(trade_date, anomaly),
        }
    finally:
        kpl.close()


class MarketDataHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._latest: dict = {}
        self._task: asyncio.Task | None = None
        self._running = False

    def connect(self, ws: WebSocket) -> None:
        self._clients.add(ws)
        logger.info("WS client connected (%d total)", len(self._clients))

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        logger.info("WS client disconnected (%d remaining)", len(self._clients))

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("MarketDataHub started (interval=%ds)", BROADCAST_INTERVAL)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("MarketDataHub stopped")

    async def _loop(self) -> None:
        while self._running:
            if self._clients:
                try:
                    data = await asyncio.to_thread(_fetch_market_data)
                    self._latest = data
                    msg = json.dumps({"type": "market_update", "data": data}, ensure_ascii=False)
                    dead: list[WebSocket] = []
                    for ws in self._clients.copy():
                        try:
                            await ws.send_text(msg)
                        except Exception:
                            dead.append(ws)
                    for ws in dead:
                        self._clients.discard(ws)
                except Exception:
                    logger.exception("MarketDataHub fetch error")
            await asyncio.sleep(BROADCAST_INTERVAL)


hub = MarketDataHub()
