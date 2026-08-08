from typing import List
from fastapi import WebSocket
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def send(self, ws: WebSocket, message: str):
        await ws.send_text(message)

    async def broadcast(self, message: dict):
        import json
        text = json.dumps(message, default=str)
        to_remove = []
        for ws in self.active:
            try:
                await ws.send_text(text)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active.remove(websocket)
        except ValueError:
            pass
