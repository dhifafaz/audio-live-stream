# API : 192.168.20.239
# PORT : 18024

from typing import Optional, List
from datetime import datetime
import logging
import pytz
import sys
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import traceback
import asyncio
from pathlib import Path


# Add parent directory to path to import from root
path_this = Path(__file__).resolve().parent
path_project = path_this.parent
path_root = path_project.parent
sys.path.append(str(path_root))


from source.agents.qwen_live_audio.qwen_live_audio_agent import QwenProcessor


logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active connections
active_connections = {}

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint that handles RTSP stream processing in different focuss (audio, video, av)."""
    await websocket.accept()
    
    processor = None
    processor_task = None
    connection_id = id(websocket)
    
    try:
        # Receive initial configuration from client
        config = await websocket.receive_json()
        rtsp_url = config.get("rtsp_url")
        focus = config.get("focus", "audio").lower()  # default: audio
        
        if not rtsp_url:
            await websocket.send_json({"error": "RTSP URL required"})
            return
        
        logging.info(f"[STREAM] Starting Qwen stream ({focus}) for {rtsp_url}")
        
        await websocket.send_json({
            "type": "status",
            "message": f"Connecting to Qwen API in {focus.upper()} focus..."
        })
        
        # Choose processor based on focus
        processor = QwenProcessor(rtsp_url=rtsp_url, websocket=websocket, focus=focus)

        
        # Store and run processor
        active_connections[connection_id] = processor
        processor_task = asyncio.create_task(processor.run())


        
        # Keep WebSocket alive until stop command or disconnect
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                if message.get("command") == "stop":
                    logging.info("[STREAM] Stop command received from client.")
                    break
            except asyncio.TimeoutError:
                if processor_task.done():
                    break
                continue
            except WebSocketDisconnect:
                logging.info("[STREAM] WebSocket disconnected by client.")
                break
        
    except WebSocketDisconnect:
        logging.info("[STREAM] WebSocket disconnected by client.")
    except Exception as e:
        logging.error(f"[STREAM] WebSocket error: {e}")
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        # Cleanup resources
        logging.info("[STREAM] Cleaning up connection...")
        
        if connection_id in active_connections:
            del active_connections[connection_id]
        
        if processor:
            await processor.stop()
            if processor_task and not processor_task.done():
                processor_task.cancel()
                try:
                    await asyncio.wait_for(processor_task, timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    logging.warning("[STREAM] Processor task did not complete in time.")
        
        try:
            await websocket.close()
        except:
            pass
            
        logging.info("[STREAM] WebSocket connection fully closed.")

@app.get("/")
async def get_index():
    """Serve the HTML file"""
    with open("templates/index_qwen.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok", 
        "message": "Qwen RTSP Server is running",
        "active_connections": len(active_connections)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18024)