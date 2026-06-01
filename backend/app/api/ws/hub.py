"""WebSocket hub for real-time signal/case streaming."""
import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, channel: str, event: str, data: dict):
        frame = json.dumps({"channel": channel, "event": event, "data": data})
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(frame)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()
