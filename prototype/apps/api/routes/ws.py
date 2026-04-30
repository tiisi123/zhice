from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from apps.api.ws_hub import hub

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/market")
async def market_ws(websocket: WebSocket):
    await websocket.accept()
    if hub._latest:
        await websocket.send_text(
            json.dumps({"type": "market_update", "data": hub._latest}, ensure_ascii=False)
        )
    hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(websocket)
