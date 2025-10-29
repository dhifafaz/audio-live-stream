### API: 192.168.20.239
### PORT 18021


# import os, sys
# import asyncio
# import json
# import logging
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.responses import HTMLResponse
# from fastapi.middleware.cors import CORSMiddleware
# from typing import Optional
# import traceback
# from json_repair import repair_json
# import sys
# from pathlib import Path



# # Add parent directory to path to import from root
# path_this = Path(__file__).resolve().parent
# path_project = path_this.parent
# path_root = path_project.parent
# sys.path.append(str(path_root))

# # Import your existing processor
# from source.agents.gemini_live_audio.gemini_live_audio_agent import GeminiProcessor

# logging.basicConfig(level=logging.INFO)

# app = FastAPI()

# # Add CORS middleware - Allow all origins
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Allow all origins
#     allow_credentials=True,
#     allow_methods=["*"],  # Allow all methods
#     allow_headers=["*"],  # Allow all headers
# )

# class WebSocketRTSPProcessor(GeminiProcessor):
#     """Extended processor that sends JSON alerts via WebSocket"""
    
#     def __init__(self, rtsp_url: str, focus: str, websocket: WebSocket):
#         super().__init__(rtsp_url, focus)
#         self.websocket = websocket
#         self.is_connected = True
        
#     async def receive_text(self):
#         """Modified to parse JSON and send via WebSocket"""
#         logging.info("Response listener started with WebSocket support.")
#         while self.is_connected:
#             try:
#                 turn = self.session.receive()
                
#                 full_response = ""
#                 async for response in turn:
#                     if text := response.text:
#                         full_response += text
                
#                 # Try to parse as JSON
#                 if full_response.strip():
#                     try:
#                         # Use json_repair to fix malformed JSON
#                         repaired = repair_json(full_response)
#                         data = json.loads(repaired)
                        
#                         # Send to WebSocket
#                         await self.websocket.send_json(data)
#                         logging.info(f"Sent alert: {data}")
#                     except Exception as e:
#                         logging.warning(f"Could not parse response as JSON: {e}")
#                         # Send as raw text update
#                         await self.websocket.send_json({
#                             "type": "raw_text",
#                             "content": full_response
#                         })
#             except Exception as e:
#                 logging.error(f"Error in receive_text: {e}")
#                 if self.is_connected:
#                     await asyncio.sleep(1)
    
#     # async def receive_text(self):
#     #     logging.info("Response listener started with WebSocket support.")
#     #     buffer = ""  # Untuk menampung potongan streaming JSON
        
#     #     while self.is_connected:
#     #         try:
#     #             turn = self.session.receive()
                
#     #             async for response in turn:
#     #                 if text := response.text:
#     #                     # Strip prefix Gemini: jika ada
#     #                     text = text.replace("Gemini:", "").strip()
                        
#     #                     # Tambahkan ke buffer
#     #                     buffer += text
                        
#     #                     # Coba split per JSON object jika ada }{ gabung
#     #                     possible_jsons = buffer.split("}{")
#     #                     for i, pj in enumerate(possible_jsons):
#     #                         if not pj.strip():
#     #                             continue
#     #                         if not pj.startswith("{"):
#     #                             pj = "{" + pj
#     #                         if not pj.endswith("}"):
#     #                             pj = pj + "}"
#     #                         try:
#     #                             repaired = repair_json(pj)
#     #                             data = json.loads(repaired)
#     #                             await self.websocket.send_json(data)
#     #                             logging.info(f"Sent alert: {data}")
                                
#     #                             # Clear buffer after sending last complete JSON
#     #                             buffer = "" if i == len(possible_jsons)-1 else possible_jsons[i+1]
#     #                         except Exception as e:
#     #                             # JSON belum lengkap atau error, simpan di buffer
#     #                             buffer = pj
#     #                             logging.debug(f"Partial JSON, waiting for more chunks: {e}")
#     #         except Exception as e:
#     #             logging.error(f"Error in receive_text: {e}")
#     #             if self.is_connected:
#     #                 await asyncio.sleep(1)

# @app.websocket("/ws/stream")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
    
#     try:
#         # Wait for initial configuration
#         config = await websocket.receive_json()
#         rtsp_url = config.get("rtsp_url")
#         focus = config.get("focus", "audio_only")
#         websocket=websocket
        
#         if not rtsp_url:
#             await websocket.send_json({"error": "RTSP URL required"})
#             return
        
#         logging.info(f"Starting stream processing for {rtsp_url}")
        
#         # Send initial status
#         await websocket.send_json({
#             "type": "status",
#             "message": "Connecting to stream..."
#         })
        
#         # Create processor
#         processor = WebSocketRTSPProcessor(rtsp_url=rtsp_url, focus=focus, websocket=websocket)
        
#         # Run processor
#         await processor.run()
        
#     except WebSocketDisconnect:
#         logging.info("WebSocket disconnected")
#     except Exception as e:
#         logging.error(f"WebSocket error: {e}")
#         traceback.print_exc()
#         try:
#             await websocket.send_json({
#                 "type": "error",
#                 "message": str(e)
#             })
#         except:
#             pass

# @app.get("/")
# async def get_index():
#     # Serve the HTML file
#     with open("templates/index_gemini.html", "r") as f:
#         return HTMLResponse(content=f.read())

# @app.get("/health")
# async def health_check():
#     """Health check endpoint"""
#     return {"status": "ok", "message": "Server is running"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=18021)









### API: 192.168.20.239
### PORT 18021

# import os, sys
# import asyncio
# import json
# import logging
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.responses import HTMLResponse
# from fastapi.middleware.cors import CORSMiddleware
# from typing import Optional
# import traceback
# from json_repair import repair_json
# import sys
# from pathlib import Path

# # Add parent directory to path
# path_this = Path(__file__).resolve().parent
# path_project = path_this.parent
# path_root = path_project.parent
# sys.path.append(str(path_root))

# from source.agents.gemini_live_audio.gemini_live_audio_agent import GeminiProcessor

# logging.basicConfig(level=logging.INFO)

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# class WebSocketRTSPProcessor(GeminiProcessor):
#     """Extended processor that sends JSON alerts via WebSocket"""
    
#     def __init__(self, rtsp_url: str, focus: str, websocket: WebSocket):
#         super().__init__(rtsp_url, focus)
#         self.websocket = websocket
#         self.is_connected = True
    
#     async def text_input(self):
#         """Override: Disable console input in WebSocket mode"""
#         logging.info("💬 WebSocket mode - awaiting text messages from client")
        
#         # Task to receive messages from WebSocket client
#         try:
#             while self.running and self.is_connected:
#                 try:
#                     data = await asyncio.wait_for(
#                         self.websocket.receive_json(), 
#                         timeout=1.0
#                     )
                    
#                     if data.get("type") == "text":
#                         message = data.get("content", "")
#                         if message.lower() == "q":
#                             logging.info("Quit signal received from client.")
#                             self.running = False
#                             break
#                         await self.send_text_message(message)
#                         logging.info(f"Sent text to Gemini: {message}")
                        
#                 except asyncio.TimeoutError:
#                     continue  # No message, keep waiting
#                 except Exception as e:
#                     logging.error(f"Error receiving WS message: {e}")
#                     break
#         except Exception as e:
#             logging.error(f"text_input error: {e}")
    
#     async def receive_responses(self):
#         """Override: Parse JSON and send via WebSocket"""
#         logging.info("Response listener started with WebSocket support.")
#         buffer = ""
        
#         while self.running and self.is_connected:
#             try:
#                 turn = self.session.receive()
                
#                 async for response in turn:
#                     if text := response.text:
#                         text = text.replace("Gemini:", "").strip()
#                         buffer += text
                        
#                         # Try to parse complete JSON
#                         try:
#                             repaired = repair_json(buffer)
#                             data = json.loads(repaired)
                            
#                             # Send to WebSocket
#                             await self.websocket.send_json(data)
#                             logging.info(f"✅ Sent JSON: {json.dumps(data, indent=2)}")
#                             buffer = ""  # Clear buffer
                            
#                         except Exception as parse_error:
#                             # JSON not complete yet, keep in buffer
#                             # Send partial update
#                             await self.websocket.send_json({
#                                 "type": "partial_text",
#                                 "content": text
#                             })
#                             logging.debug(f"Partial JSON buffered: {len(buffer)} chars")
                        
#                         await asyncio.sleep(0)  # Yield control
                        
#             except Exception as e:
#                 logging.error(f"Error in receive_responses: {e}")
#                 if self.running and self.is_connected:
#                     await asyncio.sleep(0.1)

# @app.websocket("/ws/stream")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     processor = None
    
#     try:
#         # Wait for config
#         config = await websocket.receive_json()
#         rtsp_url = config.get("rtsp_url")
#         focus = config.get("focus", "audio_video")
        
#         if not rtsp_url:
#             await websocket.send_json({"error": "RTSP URL required"})
#             return
        
#         logging.info(f"Starting stream processing for {rtsp_url}")
        
#         await websocket.send_json({
#             "type": "status",
#             "message": "Connecting to stream..."
#         })
        
#         # Create processor
#         processor = WebSocketRTSPProcessor(
#             rtsp_url=rtsp_url, 
#             focus=focus, 
#             websocket=websocket
#         )
        
#         # Run processor
#         await processor.run()
        
#     except WebSocketDisconnect:
#         logging.info("WebSocket disconnected")
#         if processor:
#             processor.is_connected = False
#             processor.running = False
#     except Exception as e:
#         logging.error(f"WebSocket error: {e}")
#         traceback.print_exc()
#         try:
#             await websocket.send_json({
#                 "type": "error",
#                 "message": str(e)
#             })
#         except:
#             pass
#     finally:
#         if processor:
#             await processor.stop()

# @app.get("/")
# async def get_index():
#     with open("templates/index_gemini.html", "r") as f:
#         return HTMLResponse(content=f.read())

# @app.get("/health")
# async def health_check():
#     return {"status": "ok", "message": "Server is running"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=18021)










# import os, sys
# import asyncio
# import json
# import logging
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.responses import HTMLResponse
# from fastapi.middleware.cors import CORSMiddleware
# from typing import Optional
# import traceback
# from json_repair import repair_json
# import sys
# from pathlib import Path

# # Add parent directory to path to import from root
# path_this = Path(__file__).resolve().parent
# path_project = path_this.parent
# path_root = path_project.parent
# sys.path.append(str(path_root))

# # Import your existing processor
# from source.agents.gemini_live_audio.gemini_live_audio_agent import GeminiProcessor

# logging.basicConfig(level=logging.INFO)

# app = FastAPI()

# # Add CORS middleware - Allow all origins
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# @app.websocket("/ws/stream")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     processor = None
    
#     try:
#         # Wait for initial configuration
#         config = await websocket.receive_json()
#         rtsp_url = config.get("rtsp_url")
#         focus = config.get("focus", "audio_only")
        
#         if not rtsp_url:
#             await websocket.send_json({"error": "RTSP URL required"})
#             return
        
#         logging.info(f"Starting stream processing for {rtsp_url}")
        
#         # Send initial status
#         await websocket.send_json({
#             "type": "status",
#             "message": "Connecting to stream..."
#         })
        
#         # Create processor with websocket
#         processor = GeminiProcessor(
#             rtsp_url=rtsp_url, 
#             focus=focus
#         )
        
#         # Run processor
#         await processor.run()
        
#     except WebSocketDisconnect:
#         logging.info("WebSocket disconnected")
#     except Exception as e:
#         logging.error(f"WebSocket error: {e}")
#         traceback.print_exc()
#         try:
#             await websocket.send_json({
#                 "type": "error",
#                 "message": str(e)
#             })
#         except:
#             pass
#     finally:
#         if processor:
#             await processor.stop()

# @app.get("/")
# async def get_index():
#     # Serve the HTML file
#     with open("templates/index_gemini.html", "r") as f:
#         return HTMLResponse(content=f.read())

# @app.get("/health")
# async def health_check():
#     """Health check endpoint"""
#     return {"status": "ok", "message": "Server is running"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=18021)

# API : 192.168.20.239
# PORT : 18021
# API : 192.168.20.239
# PORT : 18021

from typing import Optional, List
from datetime import datetime
import logging
import pytz
import sys
import json
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

# Import processor and prompts
from source.agents.gemini_live_audio.gemini_live_audio_agent import GeminiProcessor
try:
    from source.agents.gemini_live_audio.prompt import PROMPTS
except ImportError:
    PROMPTS = {"agent_gemini": ""}
    logging.warning("⚠️ Could not import PROMPTS, using empty default")

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
    """WebSocket endpoint that handles RTSP stream processing in different focus modes (audio, video, av)."""
    await websocket.accept()
    
    processor = None
    processor_task = None
    connection_id = id(websocket)
    
    try:
        # Receive initial configuration from client
        config = await websocket.receive_json()
        rtsp_url = config.get("rtsp_url")
        focus = config.get("focus", "audio_video").lower()  # default: audio_video
        
        if not rtsp_url:
            await websocket.send_json({"error": "RTSP URL required"})
            return
        
        logging.info(f"[STREAM] Starting Gemini stream ({focus}) for {rtsp_url}")
        
        await websocket.send_json({
            "type": "status",
            "message": f"Connecting to Gemini API in {focus.upper()} mode..."
        })
        
        # Always use default prompt from PROMPTS
        system_prompt = PROMPTS.get("agent_gemini", "")
        
        # Create processor
        processor = GeminiProcessor(
            rtsp_url=rtsp_url,
            websocket=websocket,
            focus=focus,
            system_prompt=system_prompt,
            provider="gemini"
        )
        
        # Store and run processor
        active_connections[connection_id] = processor
        processor_task = asyncio.create_task(processor.run())
        
        logging.info(f"[STREAM] Processor started (Connection ID: {connection_id})")
        
        # Keep WebSocket alive until stop command or disconnect
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                if message.get("command") == "stop":
                    logging.info("[STREAM] Stop command received from client.")
                    break
            except asyncio.TimeoutError:
                if processor_task.done():
                    logging.info("[STREAM] Processor task completed.")
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
    try:
        html_path = Path(__file__).parent / "templates" / "index_gemini.html"
        with open(html_path, "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>404 - index_gemini.html not found</h1>",
            status_code=404
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Gemini RTSP Server is running",
        "active_connections": len(active_connections)
    }


if __name__ == "__main__":
    import uvicorn
    
    logging.info("🚀 Starting Gemini Live Stream API Server")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=18021,
        log_level="info"
    )