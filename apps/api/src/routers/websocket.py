"""WebSocket endpoint for real-time crawl progress streaming."""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import structlog

logger = structlog.get_logger()

router = APIRouter()

# In-memory connection manager (for single-instance; use Redis PubSub for multi-instance)
class ConnectionManager:
    """Manage WebSocket connections per job."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast(self, job_id: str, message: dict):
        """Send a message to all connections for a job."""
        if job_id in self.active_connections:
            data = json.dumps(message)
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_text(data)
                except Exception:
                    pass


manager = ConnectionManager()


@router.websocket("/jobs/{job_id}/stream")
async def job_progress_stream(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for streaming crawl progress events."""
    await manager.connect(job_id, websocket)
    try:
        while True:
            # Keep connection alive; client can send heartbeats
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
