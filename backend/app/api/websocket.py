"""
WebSocket support for real-time job updates.
Provides live streaming of OCR processing status.
"""

from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set, Optional
import asyncio
import json
from datetime import datetime

from ..auth import verify_token, TokenData
from ..cache_manager import cache_manager
from ..telemetry import logger

class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        # Store active connections by job_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Store connection metadata
        self.connection_info: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket, job_id: str, user_id: Optional[str] = None):
        """Accept and register WebSocket connection."""
        await websocket.accept()
        
        # Add to job connections
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)
        
        # Store metadata
        self.connection_info[websocket] = {
            "job_id": job_id,
            "user_id": user_id,
            "connected_at": datetime.utcnow()
        }
        
        logger.info(f"WebSocket connected for job {job_id}")
        
        # Send initial status
        status = await self.get_job_status(job_id)
        await websocket.send_json(status)
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        # Get connection info
        info = self.connection_info.get(websocket)
        if info:
            job_id = info["job_id"]
            
            # Remove from job connections
            if job_id in self.active_connections:
                self.active_connections[job_id].discard(websocket)
                
                # Clean up empty sets
                if not self.active_connections[job_id]:
                    del self.active_connections[job_id]
            
            # Remove metadata
            del self.connection_info[websocket]
            
            logger.info(f"WebSocket disconnected for job {job_id}")
    
    async def send_job_update(self, job_id: str, message: dict):
        """Send update to all connections watching a job."""
        if job_id in self.active_connections:
            # Send to all connections in parallel
            tasks = []
            for connection in self.active_connections[job_id].copy():
                tasks.append(self._send_safe(connection, message))
            
            await asyncio.gather(*tasks)
    
    async def _send_safe(self, websocket: WebSocket, message: dict):
        """Send message safely, handling disconnections."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        tasks = []
        for connections in self.active_connections.values():
            for connection in connections:
                tasks.append(self._send_safe(connection, message))
        
        if tasks:
            await asyncio.gather(*tasks)
    
    async def get_job_status(self, job_id: str) -> dict:
        """Get current job status."""
        status = cache_manager.get_job_status(job_id)
        if not status:
            status = {
                "state": "unknown",
                "progress": 0,
                "message": "Job not found"
            }
        return status
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self.connection_info)
    
    def get_job_watchers(self, job_id: str) -> int:
        """Get number of connections watching a job."""
        return len(self.active_connections.get(job_id, set()))

# Global connection manager
manager = ConnectionManager()

async def websocket_endpoint(
    websocket: WebSocket,
    job_id: str,
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for job status updates.
    
    Connect with: ws://localhost:8080/ws/{job_id}?token={jwt_token}
    """
    # Optional authentication
    user_id = None
    if token:
        try:
            from jose import jwt
            from ..core.config import get_settings
            settings = get_settings()
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            user_id = payload.get("sub")
        except:
            await websocket.close(code=1008, reason="Invalid token")
            return
    
    # Connect
    await manager.connect(websocket, job_id, user_id)
    
    try:
        # Start status monitoring
        while True:
            # Check for messages from client (ping/pong)
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                
                # Handle ping
                if message == "ping":
                    await websocket.send_text("pong")
                # Handle status request
                elif message == "status":
                    status = await manager.get_job_status(job_id)
                    await websocket.send_json(status)
            except asyncio.TimeoutError:
                pass
            
            # Send periodic status updates
            status = await manager.get_job_status(job_id)
            await websocket.send_json(status)
            
            # If job is complete, close connection
            if status.get("state") in ["completed", "failed", "cancelled"]:
                await websocket.send_json({
                    "type": "close",
                    "message": f"Job {status['state']}"
                })
                break
            
            # Wait before next update
            await asyncio.sleep(2)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        await websocket.close(code=1011, reason="Internal error")

# Helper function to notify job updates
async def notify_job_update(job_id: str, state: str, progress: int, result: Optional[dict] = None):
    """Notify WebSocket clients of job updates."""
    message = {
        "type": "job_update",
        "job_id": job_id,
        "state": state,
        "progress": progress,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if result:
        message["result"] = result
    
    await manager.send_job_update(job_id, message)

# Monitoring endpoint for WebSocket connections
async def websocket_stats():
    """Get WebSocket connection statistics."""
    stats = {
        "total_connections": manager.get_connection_count(),
        "jobs_watched": len(manager.active_connections),
        "connections_per_job": {
            job_id: manager.get_job_watchers(job_id)
            for job_id in manager.active_connections
        }
    }
    return stats