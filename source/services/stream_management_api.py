"""
Stream Management API with SSE
FastAPI service for managing multiple RTSP streams with real-time updates
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator
from enum import Enum
import logging
import os
import sys

# ============================================================================
# PATH SETUP
# ============================================================================
# Add parent directories to Python path for module imports
path_this = os.path.dirname(os.path.abspath(__file__))
path_project = os.path.dirname(path_this)  # parent directory
path_root = os.path.dirname(path_project)   # grandparent directory

# Add to sys.path to enable 'from source.agents...' imports
sys.path.insert(0, path_root)
sys.path.insert(0, path_project)
sys.path.insert(0, path_this)

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
import uvicorn
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# MODELS
# ============================================================================

class StreamMode(str, Enum):
    """Stream processing modes"""
    AUDIO = "audio"
    AUDIO_VIDEO = "audio_video"
    VIDEO = "video"


class EngineType(str, Enum):
    """AI Engine types"""
    QWEN = "qwen"
    GEMINI = "gemini"


class StreamStatus(str, Enum):
    """Stream processing status"""
    REGISTERED = "registered"
    QUEUED = "queued"
    PROCESSING = "processing"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


class RTSPCredentials(BaseModel):
    """RTSP authentication credentials"""
    username: str
    password: str


class StreamConfiguration(BaseModel):
    """Stream configuration model"""
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    rtsp_url: str = Field(..., description="RTSP stream URL")
    credentials: RTSPCredentials
    mode: StreamMode = Field(default=StreamMode.AUDIO)
    engine: EngineType = Field(default=EngineType.QWEN)
    session_id: Optional[str] = None
    status: StreamStatus = Field(default=StreamStatus.REGISTERED)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Optional[Dict] = Field(default_factory=dict)

    @field_validator('rtsp_url')
    @classmethod
    def validate_rtsp_url(cls, v):
        if not v.startswith('rtsp://'):
            raise ValueError('URL must start with rtsp://')
        return v

    def get_full_rtsp_url(self) -> str:
        """Construct full RTSP URL with credentials"""
        from urllib.parse import urlparse, urlunparse
        
        parsed = urlparse(self.rtsp_url)
        
        # Insert credentials into URL
        netloc_with_auth = f"{self.credentials.username}:{self.credentials.password}@{parsed.hostname}"
        if parsed.port:
            netloc_with_auth += f":{parsed.port}"
        
        return urlunparse((
            parsed.scheme,
            netloc_with_auth,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))


class StreamUpdate(BaseModel):
    """Model for updating stream configuration"""
    rtsp_url: Optional[str] = None
    credentials: Optional[RTSPCredentials] = None
    mode: Optional[StreamMode] = None
    engine: Optional[EngineType] = None
    status: Optional[StreamStatus] = None
    metadata: Optional[Dict] = None


class StreamResponse(BaseModel):
    """Response model for stream operations"""
    success: bool
    message: str
    stream_id: Optional[str] = None
    data: Optional[Dict] = None


# ============================================================================
# STORAGE LAYER (JSON-based, easy to migrate to MongoDB)
# ============================================================================

class JSONStorage:
    """JSON file storage with MongoDB-like interface"""
    
    def __init__(self, storage_path: str = "stream_data.json"):
        self.storage_path = Path(storage_path)
        self._ensure_storage()
        self._lock = asyncio.Lock()
    
    def _ensure_storage(self):
        """Initialize storage file if it doesn't exist"""
        if not self.storage_path.exists():
            self._write_data({"streams": {}, "sessions": {}})
    
    def _read_data(self) -> Dict:
        """Read data from JSON file"""
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading storage: {e}")
            return {"streams": {}, "sessions": {}}
    
    def _write_data(self, data: Dict):
        """Write data to JSON file"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error writing storage: {e}")
    
    async def create_stream(self, config: StreamConfiguration) -> str:
        """Create new stream configuration"""
        async with self._lock:
            data = self._read_data()
            config.updated_at = datetime.now()
            data["streams"][config.id] = config.dict()
            self._write_data(data)
            logger.info(f"Created stream: {config.id}")
            return config.id
    
    async def get_stream(self, stream_id: str) -> Optional[StreamConfiguration]:
        """Get stream configuration by ID"""
        data = self._read_data()
        stream_data = data["streams"].get(stream_id)
        if stream_data:
            return StreamConfiguration(**stream_data)
        return None
    
    async def get_all_streams(self) -> List[StreamConfiguration]:
        """Get all stream configurations"""
        data = self._read_data()
        return [StreamConfiguration(**s) for s in data["streams"].values()]
    
    async def update_stream(self, stream_id: str, update: StreamUpdate) -> bool:
        """Update stream configuration"""
        async with self._lock:
            data = self._read_data()
            if stream_id not in data["streams"]:
                return False
            
            stream = data["streams"][stream_id]
            update_dict = update.dict(exclude_unset=True)
            
            # Update fields
            for key, value in update_dict.items():
                if value is not None:
                    stream[key] = value
            
            stream["updated_at"] = datetime.now().isoformat()
            self._write_data(data)
            logger.info(f"Updated stream: {stream_id}")
            return True
    
    async def update_stream_status(self, stream_id: str, status: StreamStatus, 
                                   error_message: Optional[str] = None) -> bool:
        """Update stream status"""
        async with self._lock:
            data = self._read_data()
            if stream_id not in data["streams"]:
                return False
            
            data["streams"][stream_id]["status"] = status.value
            data["streams"][stream_id]["updated_at"] = datetime.now().isoformat()
            
            if error_message:
                data["streams"][stream_id]["error_message"] = error_message
            
            self._write_data(data)
            return True
    
    async def delete_stream(self, stream_id: str) -> bool:
        """Delete stream configuration"""
        async with self._lock:
            data = self._read_data()
            if stream_id in data["streams"]:
                del data["streams"][stream_id]
                self._write_data(data)
                logger.info(f"Deleted stream: {stream_id}")
                return True
            return False


# ============================================================================
# STREAM PROCESSOR MANAGER
# ============================================================================

class StreamProcessor:
    """Manages individual stream processing"""
    
    def __init__(self, config: StreamConfiguration, storage: JSONStorage):
        self.config = config
        self.storage = storage
        self.task: Optional[asyncio.Task] = None
        self.is_running = False
        self._subscribers: List[asyncio.Queue] = []
    
    async def start(self):
        """Start stream processing"""
        if self.is_running:
            logger.warning(f"Stream {self.config.id} already running")
            return
        
        self.is_running = True
        await self.storage.update_stream_status(self.config.id, StreamStatus.PROCESSING)
        
        # Start processing task
        self.task = asyncio.create_task(self._process_stream())
        logger.info(f"Started processor for stream: {self.config.id}")
    
    async def stop(self):
        """Stop stream processing"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        await self.storage.update_stream_status(self.config.id, StreamStatus.STOPPED)
        logger.info(f"Stopped processor for stream: {self.config.id}")
    
    async def _process_stream(self):
        """Main stream processing loop"""
        try:
            await self.storage.update_stream_status(self.config.id, StreamStatus.ACTIVE)
            
            # Import processors dynamically based on engine
            if self.config.engine == EngineType.QWEN:
                from source.agents.qwen_live_audio.qwen_live_audio_agent import QwenStreamProcessor
                processor_class = QwenStreamProcessor
            else:  # GEMINI
                from source.agents.gemini_live_audio.gemini_live_audio_agent import GeminiStreamProcessor
                processor_class = GeminiStreamProcessor
            
            # Create processor instance
            full_rtsp_url = self.config.get_full_rtsp_url()
            if self.config.engine == EngineType.QWEN:
                processor = processor_class(
                    rtsp_url=full_rtsp_url,
                    focus=self.config.mode.value,
                    websocket=settings.WEBSOCKET_URL_QWEN,
                    provider=self.config.engine.value
                )
            else:
                processor = processor_class(
                    rtsp_url=full_rtsp_url,
                    focus=self.config.mode.value
                )
            
            # Broadcast start event
            await self._broadcast_event({
                "type": "stream_started",
                "stream_id": self.config.id,
                "timestamp": datetime.now().isoformat()
            })
            
            # Run processor
            await processor.run()
            
        except Exception as e:
            logger.error(f"Error processing stream {self.config.id}: {e}", exc_info=True)
            await self.storage.update_stream_status(
                self.config.id, 
                StreamStatus.ERROR, 
                str(e)
            )
            await self._broadcast_event({
                "type": "stream_error",
                "stream_id": self.config.id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    async def _broadcast_event(self, event: Dict):
        """Broadcast event to all subscribers"""
        dead_queues = []
        for queue in self._subscribers:
            try:
                await queue.put(event)
            except Exception as e:
                logger.error(f"Error broadcasting to subscriber: {e}")
                dead_queues.append(queue)
        
        # Remove dead queues
        for queue in dead_queues:
            self._subscribers.remove(queue)
    
    def subscribe(self, queue: asyncio.Queue):
        """Add event subscriber"""
        self._subscribers.append(queue)
    
    def unsubscribe(self, queue: asyncio.Queue):
        """Remove event subscriber"""
        if queue in self._subscribers:
            self._subscribers.remove(queue)


class ProcessorManager:
    """Gateway for managing multiple stream processors"""
    
    def __init__(self, storage: JSONStorage):
        self.storage = storage
        self.processors: Dict[str, StreamProcessor] = {}
        self._event_subscribers: List[asyncio.Queue] = []
    
    async def assign_work(self, stream_id: str) -> bool:
        """Assign stream to processor"""
        try:
            config = await self.storage.get_stream(stream_id)
            if not config:
                logger.error(f"Stream not found: {stream_id}")
                return False
            
            # Check if already processing
            if stream_id in self.processors:
                logger.warning(f"Stream {stream_id} already assigned")
                return False
            
            # Create and start processor
            processor = StreamProcessor(config, self.storage)
            self.processors[stream_id] = processor
            
            # Subscribe processor to manager events
            for queue in self._event_subscribers:
                processor.subscribe(queue)
            
            await processor.start()
            
            await self._broadcast_event({
                "type": "work_assigned",
                "stream_id": stream_id,
                "engine": config.engine.value,
                "mode": config.mode.value,
                "timestamp": datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error assigning work for {stream_id}: {e}", exc_info=True)
            return False
    
    async def remove_work(self, stream_id: str) -> bool:
        """Remove stream from processor"""
        if stream_id not in self.processors:
            return False
        
        processor = self.processors[stream_id]
        await processor.stop()
        del self.processors[stream_id]
        
        await self._broadcast_event({
            "type": "work_removed",
            "stream_id": stream_id,
            "timestamp": datetime.now().isoformat()
        })
        
        return True
    
    async def get_active_streams(self) -> List[str]:
        """Get list of actively processing streams"""
        return list(self.processors.keys())
    
    def subscribe(self, queue: asyncio.Queue):
        """Subscribe to manager events"""
        self._event_subscribers.append(queue)
        
        # Subscribe to all existing processors
        for processor in self.processors.values():
            processor.subscribe(queue)
    
    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from manager events"""
        if queue in self._event_subscribers:
            self._event_subscribers.remove(queue)
        
        # Unsubscribe from all processors
        for processor in self.processors.values():
            processor.unsubscribe(queue)
    
    async def _broadcast_event(self, event: Dict):
        """Broadcast event to all subscribers"""
        dead_queues = []
        for queue in self._event_subscribers:
            try:
                await queue.put(event)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
                dead_queues.append(queue)
        
        for queue in dead_queues:
            self._event_subscribers.remove(queue)


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Stream Management API",
    description="API Gateway for managing multiple RTSP audio/video streams with SSE",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates directory
from pathlib import Path
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Initialize storage and manager
storage = JSONStorage("stream_data.json")
manager = ProcessorManager(storage)


# ============================================================================
# HOME ENDPOINT
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Serve the stream management dashboard
    """
    return templates.TemplateResponse("stream_dashboard.html", {"request": request})


# ============================================================================
# SSE ENDPOINT
# ============================================================================

@app.get("/api/events")
async def stream_events(request: Request) -> StreamingResponse:
    """
    Server-Sent Events endpoint for real-time stream updates
    
    Event types:
    - stream_created: New stream registered
    - stream_updated: Stream configuration updated
    - stream_deleted: Stream removed
    - work_assigned: Stream assigned to processor
    - work_removed: Stream removed from processor
    - stream_started: Processing started
    - stream_error: Processing error occurred
    """
    
    async def event_generator() -> AsyncGenerator[str, None]:
        queue = asyncio.Queue()
        manager.subscribe(queue)
        
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("Client disconnected from SSE")
                    break
                
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"
                
        except asyncio.CancelledError:
            logger.info("SSE stream cancelled")
        finally:
            manager.unsubscribe(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================================
# CRUD ENDPOINTS
# ============================================================================

@app.post("/api/register", response_model=StreamResponse)
async def register_stream(
    config: StreamConfiguration,
    background_tasks: BackgroundTasks
) -> StreamResponse:
    """
    Register a new stream for monitoring
    
    - **rtsp_url**: RTSP stream URL (without credentials)
    - **credentials**: Username and password for RTSP
    - **mode**: audio, audio_video, or video
    - **engine**: qwen or gemini
    """
    try:
        # Create stream in storage
        stream_id = await storage.create_stream(config)
        
        # Broadcast creation event
        await manager._broadcast_event({
            "type": "stream_created",
            "stream_id": stream_id,
            "mode": config.mode.value,
            "engine": config.engine.value,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Registered stream: {stream_id}")
        
        return StreamResponse(
            success=True,
            message="Stream registered successfully",
            stream_id=stream_id,
            data=config.dict()
        )
        
    except Exception as e:
        logger.error(f"Error registering stream: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/streams", response_model=List[StreamConfiguration])
async def get_all_streams():
    """Get all registered streams"""
    try:
        streams = await storage.get_all_streams()
        return streams
    except Exception as e:
        logger.error(f"Error getting streams: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/streams/{stream_id}", response_model=StreamConfiguration)
async def get_stream(stream_id: str):
    """Get specific stream by ID"""
    try:
        stream = await storage.get_stream(stream_id)
        if not stream:
            raise HTTPException(status_code=404, detail="Stream not found")
        return stream
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stream: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/streams/{stream_id}", response_model=StreamResponse)
async def update_stream(stream_id: str, update: StreamUpdate):
    """Update stream configuration"""
    try:
        success = await storage.update_stream(stream_id, update)
        if not success:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        # Broadcast update event
        await manager._broadcast_event({
            "type": "stream_updated",
            "stream_id": stream_id,
            "timestamp": datetime.now().isoformat()
        })
        
        return StreamResponse(
            success=True,
            message="Stream updated successfully",
            stream_id=stream_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating stream: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/streams/{stream_id}", response_model=StreamResponse)
async def delete_stream(stream_id: str):
    """Delete stream configuration"""
    try:
        # Stop processing if active
        if stream_id in manager.processors:
            await manager.remove_work(stream_id)
        
        # Delete from storage
        success = await storage.delete_stream(stream_id)
        if not success:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        # Broadcast deletion event
        await manager._broadcast_event({
            "type": "stream_deleted",
            "stream_id": stream_id,
            "timestamp": datetime.now().isoformat()
        })
        
        return StreamResponse(
            success=True,
            message="Stream deleted successfully",
            stream_id=stream_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting stream: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WORK MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/streams/{stream_id}/start", response_model=StreamResponse)
async def start_stream_processing(stream_id: str):
    """Start processing a registered stream"""
    try:
        # Check if stream exists
        stream = await storage.get_stream(stream_id)
        if not stream:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        # Assign work to processor
        success = await manager.assign_work(stream_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to start processing")
        
        return StreamResponse(
            success=True,
            message="Stream processing started",
            stream_id=stream_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting stream: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/streams/{stream_id}/stop", response_model=StreamResponse)
async def stop_stream_processing(stream_id: str):
    """Stop processing a stream"""
    try:
        success = await manager.remove_work(stream_id)
        if not success:
            raise HTTPException(status_code=404, detail="Stream not processing")
        
        return StreamResponse(
            success=True,
            message="Stream processing stopped",
            stream_id=stream_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping stream: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/streams/active", response_model=List[str])
async def get_active_streams():
    """Get list of actively processing streams"""
    try:
        active = await manager.get_active_streams()
        return active
    except Exception as e:
        logger.error(f"Error getting active streams: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_streams": len(manager.processors),
        "total_streams": len(await storage.get_all_streams())
    }


@app.get("/api/info")
async def get_info():
    """Get API information"""
    return {
        "name": "Stream Management API",
        "version": "1.0.0",
        "description": "Gateway for managing multiple RTSP audio/video streams",
        "supported_engines": [e.value for e in EngineType],
        "supported_modes": [m.value for m in StreamMode],
        "endpoints": {
            "register": "POST /api/register",
            "streams": "GET /api/streams",
            "stream_detail": "GET /api/streams/{id}",
            "update": "PUT /api/streams/{id}",
            "delete": "DELETE /api/streams/{id}",
            "start": "POST /api/streams/{id}/start",
            "stop": "POST /api/streams/{id}/stop",
            "active": "GET /api/streams/active",
            "events": "GET /api/events (SSE)"
        }
    }


# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("=" * 60)
    logger.info("Stream Management API Starting...")
    logger.info("=" * 60)
    logger.info(f"Storage: {storage.storage_path}")
    logger.info(f"Supported Engines: {[e.value for e in EngineType]}")
    logger.info(f"Supported Modes: {[m.value for m in StreamMode]}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Stream Management API...")
    
    # Stop all active processors
    for stream_id in list(manager.processors.keys()):
        await manager.remove_work(stream_id)
    
    logger.info("Shutdown complete")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Stream Management API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    uvicorn.run(
        "stream_management_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )