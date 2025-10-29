"""
Multi Body Cam System Management API
Manages multiple body cameras simultaneously with batch operations
Uses JSON storage
API: 192.168.20.239
PORT: 18020
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiofiles
import aiohttp
from collections import defaultdict

logging.basicConfig(level=logging.INFO)

# Configuration
DATA_DIR = Path("./data")
STREAMS_FILE = DATA_DIR / "streams.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"
ALERTS_FILE = DATA_DIR / "alerts.json"
BODYCAMS_FILE = DATA_DIR / "bodycams.json"

# Service endpoints
SERVICES = {
    "gemini": "http://192.168.20.239:18021",
    "qwen": "http://192.168.20.239:18024"
}

app = FastAPI(title="Multi Body Cam Management System")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage for active WebSocket connections
active_bodycam_connections: Dict[str, Dict] = {}
alert_subscribers: List[WebSocket] = []

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Initialize JSON files
for file_path in [STREAMS_FILE, SESSIONS_FILE, ALERTS_FILE, BODYCAMS_FILE]:
    if not file_path.exists():
        with open(file_path, 'w') as f:
            json.dump([], f)


# ==================== Pydantic Models ====================

class BodyCamCreate(BaseModel):
    name: str
    rtsp_url: str
    service_type: str  # 'gemini' or 'qwen'
    focus: str = "audio"
    location: Optional[str] = None
    officer_id: Optional[str] = None
    config: Dict[str, Any] = {}


class BodyCamBatchCreate(BaseModel):
    bodycams: List[BodyCamCreate]


class BodyCamUpdate(BaseModel):
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    focus: Optional[str] = None
    location: Optional[str] = None
    officer_id: Optional[str] = None
    status: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class BatchOperation(BaseModel):
    bodycam_ids: List[int]
    action: str  # 'start', 'stop', 'delete'


class AlertCreate(BaseModel):
    bodycam_id: int
    alert_type: str
    severity: str = "info"
    title: str
    description: Optional[str] = None
    data: Dict[str, Any] = {}
    confidence: Optional[float] = None


# ==================== Helper Functions ====================

async def load_json(file_path: Path) -> Any:
    """Load JSON file"""
    async with aiofiles.open(file_path, 'r') as f:
        content = await f.read()
        return json.loads(content)


async def save_json(file_path: Path, data: Any):
    """Save JSON file"""
    async with aiofiles.open(file_path, 'w') as f:
        await f.write(json.dumps(data, indent=2, default=str))


def generate_id(items: List[Dict]) -> int:
    """Generate next ID"""
    if not items:
        return 1
    return max(item.get('id', 0) for item in items) + 1


def get_timestamp() -> str:
    """Get current timestamp"""
    return datetime.utcnow().isoformat() + "Z"


# ==================== Body Cam CRUD Endpoints ====================

@app.post("/api/bodycams")
async def create_bodycam(bodycam: BodyCamCreate):
    """Create single body cam"""
    bodycams = await load_json(BODYCAMS_FILE)
    
    bodycam_data = {
        "id": generate_id(bodycams),
        "name": bodycam.name,
        "rtsp_url": bodycam.rtsp_url,
        "service_type": bodycam.service_type,
        "focus": bodycam.focus,
        "location": bodycam.location,
        "officer_id": bodycam.officer_id,
        "config": bodycam.config,
        "status": "inactive",
        "created_at": get_timestamp(),
        "updated_at": get_timestamp(),
        "last_active_at": None
    }
    
    bodycams.append(bodycam_data)
    await save_json(BODYCAMS_FILE, bodycams)
    
    logging.info(f"Created body cam: {bodycam.name} (ID: {bodycam_data['id']})")
    return bodycam_data


@app.post("/api/bodycams/batch")
async def create_bodycams_batch(batch: BodyCamBatchCreate):
    """Create multiple body cams at once (BATCH INPUT)"""
    bodycams = await load_json(BODYCAMS_FILE)
    created = []
    
    for bodycam in batch.bodycams:
        bodycam_data = {
            "id": generate_id(bodycams),
            "name": bodycam.name,
            "rtsp_url": bodycam.rtsp_url,
            "service_type": bodycam.service_type,
            "focus": bodycam.focus,
            "location": bodycam.location,
            "officer_id": bodycam.officer_id,
            "config": bodycam.config,
            "status": "inactive",
            "created_at": get_timestamp(),
            "updated_at": get_timestamp(),
            "last_active_at": None
        }
        
        bodycams.append(bodycam_data)
        created.append(bodycam_data)
        logging.info(f"Created body cam: {bodycam.name} (ID: {bodycam_data['id']})")
    
    await save_json(BODYCAMS_FILE, bodycams)
    
    return {
        "message": f"Created {len(created)} body cams",
        "bodycams": created
    }


@app.get("/api/bodycams")
async def list_bodycams(
    service_type: Optional[str] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    officer_id: Optional[str] = None
):
    """List all body cams with filters"""
    bodycams = await load_json(BODYCAMS_FILE)
    
    if service_type:
        bodycams = [b for b in bodycams if b.get('service_type') == service_type]
    if status:
        bodycams = [b for b in bodycams if b.get('status') == status]
    if location:
        bodycams = [b for b in bodycams if b.get('location') == location]
    if officer_id:
        bodycams = [b for b in bodycams if b.get('officer_id') == officer_id]
    
    return bodycams


@app.get("/api/bodycams/{bodycam_id}")
async def get_bodycam(bodycam_id: int):
    """Get single body cam"""
    bodycams = await load_json(BODYCAMS_FILE)
    bodycam = next((b for b in bodycams if b['id'] == bodycam_id), None)
    
    if not bodycam:
        raise HTTPException(status_code=404, detail="Body cam not found")
    
    return bodycam


@app.put("/api/bodycams/{bodycam_id}")
async def update_bodycam(bodycam_id: int, update: BodyCamUpdate):
    """Update single body cam"""
    bodycams = await load_json(BODYCAMS_FILE)
    bodycam = next((b for b in bodycams if b['id'] == bodycam_id), None)
    
    if not bodycam:
        raise HTTPException(status_code=404, detail="Body cam not found")
    
    update_data = update.dict(exclude_unset=True)
    for key, value in update_data.items():
        bodycam[key] = value
    
    bodycam['updated_at'] = get_timestamp()
    
    await save_json(BODYCAMS_FILE, bodycams)
    logging.info(f"Updated body cam ID: {bodycam_id}")
    
    return bodycam


@app.delete("/api/bodycams/{bodycam_id}")
async def delete_bodycam(bodycam_id: int):
    """Delete single body cam"""
    bodycams = await load_json(BODYCAMS_FILE)
    bodycam = next((b for b in bodycams if b['id'] == bodycam_id), None)
    
    if not bodycam:
        raise HTTPException(status_code=404, detail="Body cam not found")
    
    bodycams = [b for b in bodycams if b['id'] != bodycam_id]
    await save_json(BODYCAMS_FILE, bodycams)
    
    logging.info(f"Deleted body cam ID: {bodycam_id}")
    return {"message": "Body cam deleted"}


# ==================== Batch Operations ====================

@app.post("/api/bodycams/batch/start")
async def start_bodycams_batch(operation: BatchOperation):
    """Start multiple body cams simultaneously (PROCESS BARENGAN)"""
    bodycams = await load_json(BODYCAMS_FILE)
    results = []
    
    # Start all body cams concurrently
    tasks = []
    for bodycam_id in operation.bodycam_ids:
        bodycam = next((b for b in bodycams if b['id'] == bodycam_id), None)
        if bodycam:
            tasks.append(start_single_bodycam(bodycam))
    
    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Update statuses in JSON
    for bodycam_id in operation.bodycam_ids:
        bodycam = next((b for b in bodycams if b['id'] == bodycam_id), None)
        if bodycam:
            bodycam['status'] = 'active'
            bodycam['last_active_at'] = get_timestamp()
    
    await save_json(BODYCAMS_FILE, bodycams)
    
    return {
        "message": f"Started {len(operation.bodycam_ids)} body cams",
        "results": results
    }


@app.post("/api/bodycams/batch/stop")
async def stop_bodycams_batch(operation: BatchOperation):
    """Stop multiple body cams simultaneously"""
    bodycams = await load_json(BODYCAMS_FILE)
    
    # Stop all connections
    for bodycam_id in operation.bodycam_ids:
        if str(bodycam_id) in active_bodycam_connections:
            # Signal stop
            active_bodycam_connections[str(bodycam_id)]['should_stop'] = True
    
    # Update statuses
    for bodycam_id in operation.bodycam_ids:
        bodycam = next((b for b in bodycams if b['id'] == bodycam_id), None)
        if bodycam:
            bodycam['status'] = 'inactive'
    
    await save_json(BODYCAMS_FILE, bodycams)
    
    return {
        "message": f"Stopped {len(operation.bodycam_ids)} body cams"
    }


@app.post("/api/bodycams/batch/delete")
async def delete_bodycams_batch(operation: BatchOperation):
    """Delete multiple body cams"""
    bodycams = await load_json(BODYCAMS_FILE)
    
    # Stop first
    for bodycam_id in operation.bodycam_ids:
        if str(bodycam_id) in active_bodycam_connections:
            active_bodycam_connections[str(bodycam_id)]['should_stop'] = True
    
    # Delete
    bodycams = [b for b in bodycams if b['id'] not in operation.bodycam_ids]
    await save_json(BODYCAMS_FILE, bodycams)
    
    return {
        "message": f"Deleted {len(operation.bodycam_ids)} body cams"
    }


async def start_single_bodycam(bodycam: Dict) -> Dict:
    """Start processing a single body cam"""
    try:
        bodycam_id = str(bodycam['id'])
        
        # Create connection info
        active_bodycam_connections[bodycam_id] = {
            'bodycam': bodycam,
            'should_stop': False,
            'task': None
        }
        
        logging.info(f"Started body cam {bodycam['name']} (ID: {bodycam['id']})")
        
        return {
            "bodycam_id": bodycam['id'],
            "name": bodycam['name'],
            "status": "started"
        }
    except Exception as e:
        logging.error(f"Failed to start body cam {bodycam['id']}: {e}")
        return {
            "bodycam_id": bodycam['id'],
            "name": bodycam['name'],
            "status": "error",
            "error": str(e)
        }


# ==================== Real-time Monitoring WebSocket ====================

@app.websocket("/ws/monitor/all")
async def monitor_all_bodycams(websocket: WebSocket):
    """Monitor all active body cams in real-time (OUTPUT BARENGAN)"""
    await websocket.accept()
    alert_subscribers.append(websocket)
    
    try:
        # Send initial status
        bodycams = await load_json(BODYCAMS_FILE)
        await websocket.send_json({
            "type": "status",
            "message": "Connected to monitoring system",
            "total_bodycams": len(bodycams),
            "active_bodycams": len([b for b in bodycams if b.get('status') == 'active'])
        })
        
        # Keep connection alive and forward all alerts
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                
                if message.get('command') == 'ping':
                    await websocket.send_json({"type": "pong"})
                elif message.get('command') == 'status':
                    bodycams = await load_json(BODYCAMS_FILE)
                    await websocket.send_json({
                        "type": "status",
                        "bodycams": bodycams
                    })
                    
            except asyncio.TimeoutError:
                continue
                
    except WebSocketDisconnect:
        logging.info("Monitor disconnected")
    finally:
        if websocket in alert_subscribers:
            alert_subscribers.remove(websocket)


@app.websocket("/ws/bodycam/{bodycam_id}")
async def stream_single_bodycam(websocket: WebSocket, bodycam_id: int):
    """Stream single body cam with real-time alerts"""
    await websocket.accept()
    
    bodycams = await load_json(BODYCAMS_FILE)
    bodycam = next((b for b in bodycams if b['id'] == bodycam_id), None)
    
    if not bodycam:
        await websocket.send_json({"error": "Body cam not found"})
        await websocket.close()
        return
    
    try:
        await websocket.send_json({
            "type": "connected",
            "bodycam_id": bodycam_id,
            "bodycam": bodycam
        })
        
        # Simulate streaming (in real implementation, connect to actual RTSP service)
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                if message.get('command') == 'stop':
                    break
            except asyncio.TimeoutError:
                continue
                
    except WebSocketDisconnect:
        logging.info(f"Body cam {bodycam_id} stream disconnected")
    finally:
        await websocket.close()


# ==================== Alert Management ====================

@app.post("/api/alerts")
async def create_alert(alert: AlertCreate):
    """Create alert and broadcast to all subscribers"""
    alerts = await load_json(ALERTS_FILE)
    
    alert_data = {
        "id": generate_id(alerts),
        "bodycam_id": alert.bodycam_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "description": alert.description,
        "data": alert.data,
        "confidence": alert.confidence,
        "created_at": get_timestamp(),
        "acknowledged": False
    }
    
    alerts.append(alert_data)
    await save_json(ALERTS_FILE, alerts)
    
    # Broadcast to all subscribers (OUTPUT BARENGAN)
    await broadcast_alert(alert_data)
    
    logging.info(f"Created alert: {alert.title} for body cam {alert.bodycam_id}")
    return alert_data


async def broadcast_alert(alert: Dict):
    """Broadcast alert to all connected WebSocket clients"""
    disconnected = []
    
    for websocket in alert_subscribers:
        try:
            await websocket.send_json({
                "type": "alert",
                "alert": alert
            })
        except:
            disconnected.append(websocket)
    
    # Remove disconnected clients
    for ws in disconnected:
        if ws in alert_subscribers:
            alert_subscribers.remove(ws)


@app.get("/api/alerts")
async def list_alerts(
    bodycam_id: Optional[int] = None,
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    limit: int = 100
):
    """List alerts with filters"""
    alerts = await load_json(ALERTS_FILE)
    
    if bodycam_id is not None:
        alerts = [a for a in alerts if a.get('bodycam_id') == bodycam_id]
    if severity:
        alerts = [a for a in alerts if a.get('severity') == severity]
    if acknowledged is not None:
        alerts = [a for a in alerts if a.get('acknowledged') == acknowledged]
    
    alerts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return alerts[:limit]


@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
    """Acknowledge an alert"""
    alerts = await load_json(ALERTS_FILE)
    alert = next((a for a in alerts if a['id'] == alert_id), None)
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert['acknowledged'] = True
    alert['acknowledged_at'] = get_timestamp()
    
    await save_json(ALERTS_FILE, alerts)
    return alert


# ==================== System Statistics ====================

@app.get("/api/stats")
async def get_statistics():
    """Get system statistics"""
    bodycams = await load_json(BODYCAMS_FILE)
    alerts = await load_json(ALERTS_FILE)
    
    return {
        "timestamp": get_timestamp(),
        "bodycams": {
            "total": len(bodycams),
            "active": len([b for b in bodycams if b.get('status') == 'active']),
            "inactive": len([b for b in bodycams if b.get('status') == 'inactive']),
            "by_service": {
                "gemini": len([b for b in bodycams if b.get('service_type') == 'gemini']),
                "qwen": len([b for b in bodycams if b.get('service_type') == 'qwen'])
            },
            "by_location": count_by_field(bodycams, 'location')
        },
        "alerts": {
            "total": len(alerts),
            "unacknowledged": len([a for a in alerts if not a.get('acknowledged')]),
            "by_severity": {
                "critical": len([a for a in alerts if a.get('severity') == 'critical']),
                "warning": len([a for a in alerts if a.get('severity') == 'warning']),
                "info": len([a for a in alerts if a.get('severity') == 'info'])
            }
        },
        "monitoring": {
            "active_connections": len(active_bodycam_connections),
            "alert_subscribers": len(alert_subscribers)
        }
    }


def count_by_field(items: List[Dict], field: str) -> Dict[str, int]:
    """Count items grouped by field"""
    counts = defaultdict(int)
    for item in items:
        value = item.get(field, 'unknown')
        counts[value] += 1
    return dict(counts)


@app.get("/api/export")
async def export_all():
    """Export all data"""
    return {
        "timestamp": get_timestamp(),
        "bodycams": await load_json(BODYCAMS_FILE),
        "alerts": await load_json(ALERTS_FILE)
    }


@app.post("/api/import")
async def import_all(data: Dict[str, Any] = Body(...)):
    """Import data"""
    if 'bodycams' in data:
        await save_json(BODYCAMS_FILE, data['bodycams'])
    if 'alerts' in data:
        await save_json(ALERTS_FILE, data['alerts'])
    
    return {"message": "Data imported successfully"}


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "ok",
        "message": "Multi Body Cam System is running",
        "active_bodycams": len(active_bodycam_connections),
        "alert_subscribers": len(alert_subscribers)
    }


@app.get("/")
async def root():
    """API documentation"""
    return {
        "name": "Multi Body Cam Management System",
        "version": "1.0.0",
        "features": [
            "✅ Batch input multiple body cams",
            "✅ Process all body cams simultaneously",
            "✅ Real-time monitoring (all cameras)",
            "✅ Unified CRUD operations",
            "✅ JSON storage"
        ],
        "endpoints": {
            "bodycams": "/api/bodycams",
            "batch_create": "/api/bodycams/batch",
            "batch_start": "/api/bodycams/batch/start",
            "batch_stop": "/api/bodycams/batch/stop",
            "alerts": "/api/alerts",
            "monitor_all": "/ws/monitor/all",
            "stats": "/api/stats",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18020)