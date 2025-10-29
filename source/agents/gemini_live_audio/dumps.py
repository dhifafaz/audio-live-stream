# import sys
# import asyncio
# import base64
# import io
# import traceback
# import argparse
# import subprocess
# import os
# import cv2
# import PIL.Image
# from loguru import logger
# from google import genai
# from textwrap import dedent
# from dotenv import load_dotenv
# from .prompt import PROMPTS

# load_dotenv()
# MODEL = "models/gemini-2.0-flash-live-001"  # Update as needed
# SEND_SAMPLE_RATE = 16000
# AUDIO_CHUNK_SIZE = 3200 



# # ----------------------
# # Constants
# # ----------------------
# CONFIG = {"response_modalities": ["TEXT"], "system_instruction": dedent(PROMPTS['agent_gemini'])}

# # ----------------------
# # Initialize Gemini client
# # ----------------------
# try:
#     client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
#     logger.info("✅ Gemini client initialized successfully.")
# except Exception as e:
#     logger.error(f"❌ Failed to initialize Gemini Client. Ensure GOOGLE_API_KEY is set. Error: {e}")
#     exit(1)


# class GeminiProcessor:
#     """Manages RTSP stream and Gemini Live API interaction."""

#     def __init__(self, rtsp_url: str, focus: str = "audio_video"):
#         self.rtsp_url = rtsp_url
#         self.focus = focus
#         self.out_queue = None
#         self.session = None

#     async def send_text(self):
#         """Asynchronously reads user input from console and sends it to API."""
#         logger.info("Text input task started. Type 'q' to quit.")
#         while True:
#             try:
#                 message = await asyncio.to_thread(input, "\nmessage > ")
#                 if message.lower() == "q":
#                     logger.info("Quit command received. Shutting down.")
#                     break
#                 await self.session.send(input=message or ".", end_of_turn=True)
#             except (BrokenPipeError, IOError):
#                 logger.warning("Input stream closed.")
#                 break

#     async def get_rtsp_video(self):
#         """Capture video frames from RTSP and put them in queue."""
#         logger.info("Starting video capture...")
#         cap = None
#         try:
#             cap = await asyncio.to_thread(cv2.VideoCapture, self.rtsp_url)
#             if not cap.isOpened():
#                 logger.error(f"Cannot open RTSP video stream: {self.rtsp_url}")
#                 return
#             while cap.isOpened():
#                 ret, frame = await asyncio.to_thread(cap.read)
#                 if not ret:
#                     logger.warning("Video stream ended or frame read failed.")
#                     break
#                 frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#                 img = PIL.Image.fromarray(frame_rgb)
#                 img.thumbnail([1024, 1024])
#                 buf = io.BytesIO()
#                 img.save(buf, format="jpeg")
#                 buf.seek(0)
#                 payload = {"mime_type": "image/jpeg", "data": base64.b64encode(buf.read()).decode('utf-8')}
#                 await self.out_queue.put(payload)
#                 await asyncio.sleep(1.0)
#         finally:
#             if cap and cap.isOpened():
#                 cap.release()
#             logger.info("Video capture finished.")

#     async def listen_rtsp_audio(self):
#         """Extract audio from RTSP using FFmpeg and enqueue PCM chunks."""
#         logger.info("Starting audio capture...")
#         command = [
#                 'ffmpeg',
#                 '-rtsp_transport', 'tcp',
#                 '-fflags', '+igndts+genpts',  
#                 '-i', self.rtsp_url,
#                 '-loglevel', 'error',
#                 '-nostats', '-hide_banner',
#                 '-f', 's16le',
#                 '-acodec', 'pcm_s16le',
#                 '-ar', str(SEND_SAMPLE_RATE),
#                 '-ac', '1',
#                 '-'
#             ]
#         proc = None
#         try:
#             proc = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#             error_task = asyncio.create_task(self._log_stderr(proc.stderr))
#             while True:
#                 audio_data = await proc.stdout.read(AUDIO_CHUNK_SIZE)
#                 if not audio_data:
#                     break
#                 await self.out_queue.put({"data": audio_data, "mime_type": "audio/pcm"})
#             return_code = await proc.wait()
#             await error_task
#             if return_code != 0:
#                 logger.error(f"FFmpeg exited with code {return_code}")
#             else:
#                 logger.info("Audio stream ended successfully.")
#         except FileNotFoundError:
#             logger.error("FFmpeg not found. Install and add to PATH.")
#         finally:
#             if proc and proc.returncode is None:
#                 proc.terminate()
#                 await proc.wait()
#             logger.info("Audio capture finished.")

#     async def _log_stderr(self, stderr):
#         while True:
#             line = await stderr.readline()
#             if not line:
#                 break
#             logger.error(f"FFmpeg Error: {line.decode().strip()}")

#     async def send_realtime(self):
#         """Send media from queue to Gemini API."""
#         logger.info("Realtime media sending started.")
#         while True:
#             payload = await self.out_queue.get()
#             await self.session.send(input=payload)
#             self.out_queue.task_done()

#     async def receive_text(self):
#         """Receive text responses from Gemini API and print to console."""
#         logger.info("Response listener started.")
#         while True:
#             turn = self.session.receive()
#             printed_prefix = False
#             async for response in turn:
#                 if text := response.text:
#                     if not printed_prefix:
#                         print("\nGemini: ", end="", flush=True)
#                         printed_prefix = True
#                     print(text, end="", flush=True)

#     async def run(self):
#         """Run all tasks concurrently."""
#         try:
#             async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
#                 self.session = session
#                 self.out_queue = asyncio.Queue(maxsize=100)
#                 async with asyncio.TaskGroup() as tg:
#                     logger.info("Connected to Gemini Live API.")

#                     send_text_task = tg.create_task(self.send_text())
#                     tg.create_task(self.send_realtime())
#                     tg.create_task(self.receive_text())

#                     if self.focus in ["audio_video", "audio_only"]:
#                         logger.info("Audio processing enabled.")
#                         tg.create_task(self.listen_rtsp_audio())

#                     if self.focus in ["audio_video", "video_only"]:
#                         logger.info("Video processing enabled.")
#                         tg.create_task(self.get_rtsp_video())

#                     await send_text_task
#                     raise asyncio.CancelledError("User requested exit.")

#         except asyncio.CancelledError:
#             logger.info("Shutting down application.")
#         except Exception as e:
#             logger.exception("Unexpected error in main loop")

# def main():
#     parser = argparse.ArgumentParser(description="Process RTSP stream with Gemini Live API.")
#     parser.add_argument("--rtsp-url", type=str, required=True)
#     parser.add_argument("--focus", type=str, default="audio_video", choices=["audio_video", "audio_only", "video_only"])
#     args = parser.parse_args()
#     processor = GeminiProcessor(rtsp_url=args.rtsp_url, focus=args.focus)
#     try:
#         asyncio.run(processor.run())
#     except KeyboardInterrupt:
#         logger.info("Keyboard interrupt received, exiting.")


# import os
# import asyncio
# import json
# import logging
# import base64
# from textwrap import dedent
# from google import genai
# from dotenv import load_dotenv
# from json_repair import repair_json
# from source.agents.base_processor import BaseStreamProcessor
# from source.agents.gemini_live_audio.prompt import PROMPTS

# load_dotenv()

# MODEL = "models/gemini-2.0-flash-live-001"
# CONFIG = {
#     "response_modalities": ["TEXT"],
#     "system_instruction": dedent(PROMPTS.get("agent_gemini", "")) if PROMPTS.get("agent_gemini") else "",
# }


# client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# class GeminiProcessor(BaseStreamProcessor):
#     """Gemini Live API processor with audio/video streaming support."""

#     def __init__(self, rtsp_url: str, focus: str = "audio_video", websocket=None):
#         super().__init__(rtsp_url, focus)
#         self.buffer = ""
#         self.websocket = websocket  # ← Pass websocket dari FastAPI

#     async def initialize_session(self):
#         self.session_context = client.aio.live.connect(model=MODEL, config=CONFIG)
#         self.session = await self.session_context.__aenter__()
#         logging.info("✅ Gemini session initialized.")

#     async def cleanup_session(self):
#         if hasattr(self, "session_context") and self.session_context:
#             await self.session_context.__aexit__(None, None, None)
#             logging.info("✅ Gemini session closed.")

#     async def send_realtime_data(self, audio_chunk=None, video_frame=None):
#         payload = {}
        
#         if audio_chunk:
#             payload["mime_type"] = "audio/pcm"
#             payload["data"] = base64.b64decode(audio_chunk)
#         elif video_frame:
#             payload["mime_type"] = "image/jpeg"
#             payload["data"] = base64.b64decode(video_frame)

#         if payload:
#             await self.session.send(input=payload)

#     async def send_text_message(self, text: str):
#         await self.session.send(input=text, end_of_turn=True)

#     async def text_input(self):
#         """Override: WebSocket mode - no console input needed."""
#         if self.websocket:
#             logging.info("💬 WebSocket mode - text input via WS messages")
#             while self.running:
#                 await asyncio.sleep(1)  # Just keep alive, text comes from WS
#         else:
#             # Fallback ke console mode
#             await super().text_input()

#     async def receive_responses(self):
#         while self.running:
#             try:
#                 turn = self.session.receive()
#                 async for response in turn:
#                     if text := response.text:
#                         text = text.replace("Gemini:", "").strip()
#                         self.buffer += text

#                         try:
#                             repaired = repair_json(self.buffer)
#                             data = json.loads(repaired)

#                             if self.websocket:
#                                 await self.websocket.send_json(data)
#                             else:
#                                 print(f"\n📦 Parsed JSON: {json.dumps(data, indent=2)}", flush=True)

#                             self.buffer = ""
#                         except Exception:
#                             if self.websocket:
#                                 await self.websocket.send_json({
#                                     "type": "raw_text",
#                                     "content": text
#                                 })
#                             else:
#                                 print(f"\n💬 Gemini: {text}", end="", flush=True)
                            
#                             await asyncio.sleep(0)
#             except Exception as e:
#                 logging.error(f"❌ Error in receive_responses: {e}")
#                 await asyncio.sleep(0.1)
