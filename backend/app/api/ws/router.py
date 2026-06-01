from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.ws.hub import manager

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Keep connection alive; client can send subscribe ops
            data = await ws.receive_text()
            # Echo back as ACK
            await ws.send_text(f'{{"ack": true, "received": {data}}}')
    except WebSocketDisconnect:
        manager.disconnect(ws)
