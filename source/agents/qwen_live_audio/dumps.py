

# import os
# import sys
# import asyncio
# import base64
# import subprocess
# import logging
# import argparse
# import json
# import time
# from textwrap import dedent
# from typing import Optional
# from .prompt import PROMPTS
# from .process_rstp_stream_qwen import RTSPStreamProcessor
# from dotenv import load_dotenv
# import dashscope
# from dashscope.audio.qwen_omni import *
# from dashscope.audio.qwen_omni.omni_realtime import (
#     AudioFormat,
#     OmniRealtimeConversation,
#     MultiModality
# )

# # -----------------------------------------------------------
# # CONFIGURATION
# # -----------------------------------------------------------
# load_dotenv()
# # Securely fetch API key from environment
# dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")


# SEND_SAMPLE_RATE = 16000
# AUDIO_CHUNK_SIZE = 1280  # 100ms chunks
# VIDEO_CHUNK_INTERVAL = 1.5  # seconds between video frame sends
# RESPONSE_INTERVAL = 2.0  # Request response every 2 seconds for real-time analysis
# RECONNECT_BACKOFF = 2.0  # seconds initial backoff for reconnect attempts
# MAX_RECONNECT_BACKOFF = 60.0

# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# # ========== CALLBACK ==========
# class QwenCallback(OmniRealtimeCallback):
#     """Callback handler for Qwen Omni API events"""

#     def __init__(self, websocket=None, loop: Optional[asyncio.AbstractEventLoop] = None):
#         self.websocket = websocket
#         self.session_id = None
#         self.accumulated_text = ""
#         # prefer an externally provided loop (the main asyncio loop)
#         self.loop = loop or asyncio.get_event_loop()

#     def on_open(self) -> None:
#         logging.info('Qwen connection opened successfully')

#     def on_close(self, close_status_code, close_msg) -> None:
#         logging.info(f'Qwen connection closed: {close_status_code} - {close_msg}')

#     def on_event(self, response: dict) -> None:
#         try:
#             event_type = response.get('type')
#             logging.info(f"Qwen Event: {event_type}")

#             if event_type == 'session.created':
#                 self.session_id = response['session']['id']
#                 logging.info(f'✓ Session started: {self.session_id}')

#             elif event_type == 'conversation.item.input_audio_transcription.completed':
#                 transcript = response.get('transcript', '')
#                 logging.info(f'🎤 Transcription: {transcript}')

#             elif event_type == 'response.text.delta':
#                 text = response.get('delta', '')
#                 logging.info(f'📝 Text delta: {text}')
#                 self.accumulated_text += text

#             elif event_type == 'response.text.done':
#                 text = response.get('text', '')
#                 logging.info(f'✓ Full text response: {text}')
#                 self._try_send_alert(text)
#                 self.accumulated_text = ""

#             elif event_type == 'response.done':
#                 logging.info('✓ Response completed')
#                 if self.accumulated_text:
#                     self._try_send_alert(self.accumulated_text)
#                     self.accumulated_text = ""

#             elif event_type == 'input_audio_buffer.speech_started':
#                 logging.info('🔊 Speech detected in audio stream')

#             elif event_type == 'input_audio_buffer.speech_stopped':
#                 logging.info('🔇 Speech ended')

#             elif event_type == 'input_audio_buffer.committed':
#                 logging.info('✓ Audio buffer committed - waiting for response')

#             elif event_type == 'conversation.item.created':
#                 item = response.get('item', {})
#                 logging.info(f'💬 Conversation item created: {item.get("type")}')

#             elif event_type == 'response.created':
#                 logging.info('📄 Response generation started')

#             elif event_type == 'response.output_item.added':
#                 logging.info('➕ Output item added to response')

#             elif event_type == 'response.content_part.added':
#                 content_part = response.get('part', {})
#                 logging.info(f'📋 Content part added: {content_part.get("type")}')

#             else:
#                 logging.debug(f'ℹ️ Other event: {event_type}')

#         except Exception as e:
#             logging.error(f'Error in callback: {e}', exc_info=True)

#     def _send_json_threadsafe(self, data: dict):
#         """Send websocket JSON safely from any thread."""
#         if not self.websocket:
#             return
#         try:
#             # Use run_coroutine_threadsafe to schedule send on the main loop
#             coro = self.websocket.send_json(data)
#             asyncio.run_coroutine_threadsafe(coro, self.loop)
#             logging.info(f'🚨 Alert sent (threadsafe): {data}')
#         except Exception as e:
#             logging.error(f'Error sending alert threadsafe: {e}', exc_info=True)

#     def _try_send_alert(self, text: str):
#         """Try to parse and send alert via websocket"""
#         if not self.websocket or not text:
#             return

#         try:
#             data = json.loads(text.strip())
#             if isinstance(data, dict) and ('alert' in data or 'description' in data):
#                 self._send_json_threadsafe(data)
#                 return
#         except json.JSONDecodeError:
#             # Try to extract JSON substring
#             try:
#                 start_idx = text.find('{')
#                 end_idx = text.rfind('}')
#                 if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
#                     json_str = text[start_idx:end_idx+1]
#                     data = json.loads(json_str)
#                     if isinstance(data, dict) and ('alert' in data or 'description' in data):
#                         self._send_json_threadsafe(data)
#                         return
#             except Exception:
#                 logging.debug('Could not extract JSON from text', exc_info=False)
#         except Exception as e:
#             logging.error(f'Unexpected error parsing alert text: {e}', exc_info=True)


# # ========== BASE CLASS ==========
# class BaseRTSPProcessor:
#     def __init__(self, rtsp_url: str, websocket=None):
#         self.rtsp_url = rtsp_url
#         self.websocket = websocket
#         self.conversation: Optional[OmniRealtimeConversation] = None
#         self.loop = asyncio.get_event_loop()
#         self.callback = QwenCallback(websocket, loop=self.loop)
#         self.is_running = False
#         self.ffmpeg_process = None
#         self._reconnect_attempts = 0
#         self._closed_by_user = False

#     async def setup_qwen_connection(self, modalities):
#         """Initialize connection to Qwen Omni API with simple reconnect/backoff"""
#         logging.info(f'Initializing Qwen Omni connection for {modalities}...')

#         # Build conversation object
#         self.conversation = OmniRealtimeConversation(
#             model='qwen3-omni-flash-realtime',
#             callback=self.callback,
#             url="wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
#         )

#         # Try connecting with exponential backoff
#         backoff = RECONNECT_BACKOFF
#         while not self._closed_by_user:
#             try:
#                 # connect may be blocking so run in thread
#                 await asyncio.to_thread(self.conversation.connect)
#                 logging.info("✅ Connected to Qwen Omni")
#                 # reset reconnect attempts and break
#                 self._reconnect_attempts = 0
#                 break
#             except Exception as e:
#                 self._reconnect_attempts += 1
#                 logging.error(f"Failed to connect to Qwen Omni (attempt {self._reconnect_attempts}): {e}")
#                 await asyncio.sleep(backoff)
#                 backoff = min(backoff * 2, MAX_RECONNECT_BACKOFF)

#         # Determine settings based on modalities
#         audio_enabled = "audio" in modalities
#         video_enabled = "video" in modalities

#         audio_format = AudioFormat.PCM_16000HZ_MONO_16BIT if audio_enabled else None
#         video_format = "H264" if video_enabled else None

#         session_params = {
#             'voice': 'Cherry',
#             'output_modalities': [MultiModality.TEXT],
#             'enable_turn_detection': False,
#             'instructions': dedent(PROMPTS['agent_qwen']),
#         }

#         if audio_format:
#             session_params['input_audio_format'] = audio_format
#             session_params['enable_input_audio_transcription'] = True

#         if video_format:
#             session_params['input_video_format'] = video_format

#         await asyncio.to_thread(self.conversation.update_session, **session_params)
#         logging.info('Qwen Omni session configured successfully')

#     async def ensure_conversation_connected(self):
#         """Ensure conversation is connected; try reconnect if needed."""
#         if not self.conversation:
#             await self.setup_qwen_connection(["audio", "video"])
#             return

#         # If conversation has a close method/flag, check and reconnect - library specifics may vary
#         try:
#             # call a harmless method or attribute access to test; adapt if library exposes 'is_open'
#             # We'll attempt a no-op update_session to verify connectivity
#             await asyncio.to_thread(self.conversation.commit)
#         except Exception as e:
#             logging.warning(f'Conversation commit failed, attempting reconnect: {e}')
#             await self.setup_qwen_connection(["audio", "video"])

#     async def cleanup_ffmpeg(self):
#         """Terminate ffmpeg cleanly"""
#         if self.ffmpeg_process and self.ffmpeg_process.returncode is None:
#             try:
#                 logging.info("Terminating ffmpeg process...")
#                 self.ffmpeg_process.terminate()
#                 await asyncio.wait_for(self.ffmpeg_process.wait(), timeout=3.0)
#             except asyncio.TimeoutError:
#                 logging.warning("ffmpeg did not exit, killing...")
#                 self.ffmpeg_process.kill()
#                 await self.ffmpeg_process.wait()
#         self.ffmpeg_process = None

#     async def _log_stderr(self, stderr):
#         """Helper coroutine to read and log stderr FFmpeg."""
#         while True:
#             line = await stderr.readline()
#             if not line:
#                 break
#             # keep stderr as ERROR as it often contains ffmpeg warnings/errors
#             logging.error(f"[FFMPEG_ERROR] {line.decode(errors='ignore').strip()}")
#         logging.info("[FFMPEG_ERROR] Stderr stream ended.")

#     async def stop(self):
#         logging.info("Stopping processor...")
#         try:
#             if getattr(self, "qwen_conversation", None):
#                 await self.qwen_conversation.close()
#             else:
#                 logging.warning("No active Qwen conversation to close.")
#         except Exception as e:
#             logging.error(f"Error closing Qwen conversation: {e}")

#             await self.cleanup_ffmpeg()

#             if hasattr(self, 'conversation') and self.conversation:
#                 logging.info("[STREAM] Closing Qwen conversation...")
#                 try:
#                     await asyncio.to_thread(self.conversation.close)
#                 except Exception as e:
#                     logging.error(f"Error closing conversation: {e}", exc_info=True)

#             logging.info("[STREAM] Cleanup complete.")


# # ========== AUDIO + VIDEO PROCESSOR WITH REAL-TIME RESPONSES ==========
# class RTSPStreamProcessorAV(BaseRTSPProcessor):
#     """Extracts both audio and video, sends to Qwen Omni with periodic real-time responses"""

#     async def run(self):
#         self.is_running = True
#         try:
#             await self.setup_qwen_connection(["audio", "video"])

#             # Run audio, video, and periodic response generation concurrently
#             await asyncio.gather(
#                 self._read_audio(),
#                 self._read_video(),
#                 self._periodic_response(),
#                 return_exceptions=True
#             )

#         except Exception as e:
#             logging.error(f"[STREAM] Error during AV run: {e}", exc_info=True)
#         finally:
#             await self.stop()
#         logging.info("[STREAM] AV Processor finished.")

#     async def _periodic_response(self):
#         """Periodically commit buffer and request responses from Qwen for real-time analysis"""
#         try:
#             await asyncio.sleep(RESPONSE_INTERVAL)

#             response_count = 0
#             while self.is_running:
#                 if self.conversation:
#                     try:
#                         response_count += 1
#                         logging.info(f"[STREAM] ⏰ Requesting response #{response_count} from Qwen...")
#                         # ensure connected
#                         await self.ensure_conversation_connected()
#                         await asyncio.to_thread(self.conversation.commit)
#                         await asyncio.to_thread(self.conversation.create_response)
#                         logging.info(f"[STREAM] ✓ Response #{response_count} request sent")
#                     except Exception as e:
#                         logging.error(f"[STREAM] Error requesting response: {e}", exc_info=True)
#                 else:
#                     logging.warning("[STREAM] No conversation object; skipping response request.")

#                 # Wait before next response
#                 await asyncio.sleep(RESPONSE_INTERVAL)

#         except asyncio.CancelledError:
#             logging.info("[STREAM] Periodic response task cancelled")
#         except Exception as e:
#             logging.error(f"[STREAM] Error in periodic response: {e}", exc_info=True)

#     async def _read_audio(self):
#         """Extract audio PCM safely with stable timestamps"""
#         # Stabilized ffmpeg command
#         command_audio = [
#             'ffmpeg',
#             '-fflags', '+genpts+discardcorrupt+nobuffer',
#             '-flags', 'low_delay',
#             '-use_wallclock_as_timestamps', '1',
#             '-avoid_negative_ts', 'make_zero',
#             '-err_detect', 'ignore_err',
#             '-rtsp_transport', 'tcp',
#             '-i', self.rtsp_url,
#             '-vn', '-f', 's16le',
#             '-acodec', 'pcm_s16le',
#             '-ar', str(SEND_SAMPLE_RATE),
#             '-ac', '1', '-'
#         ]
#         logging.info(f"Starting ffmpeg audio with: {' '.join(command_audio[:6])} ...")
#         proc = await asyncio.create_subprocess_exec(
#             *command_audio,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE
#         )
#         self.ffmpeg_process = proc

#         stderr_task = asyncio.create_task(self._log_stderr(proc.stderr))

#         try:
#             while self.is_running:
#                 data = await proc.stdout.read(AUDIO_CHUNK_SIZE)
#                 if not data:
#                     logging.warning("[STREAM] FFmpeg audio stream ended (stdout closed).")
#                     break

#                 b64 = base64.b64encode(data).decode()
#                 if self.conversation:
#                     try:
#                         await asyncio.to_thread(self.conversation.append_audio, b64)
#                     except Exception as e:
#                         logging.warning(f"[STREAM] append_audio failed: {e}. Attempting reconnect.")
#                         await self.setup_qwen_connection(["audio", "video"])
#                 else:
#                     logging.debug("[STREAM] No conversation; skipping append_audio.")
#         except Exception as e:
#             logging.error(f"[STREAM] Error in AV audio read loop: {e}", exc_info=True)
#         finally:
#             await stderr_task
#             logging.info("[STREAM] AV Audio read loop finished.")


#     async def _read_video(self):
#         """Extract video frames safely as JPEG with stable timestamps"""
#         command_video = [
#             'ffmpeg',
#             '-fflags', '+genpts+discardcorrupt+nobuffer',
#             '-flags', 'low_delay',
#             '-use_wallclock_as_timestamps', '1',
#             '-avoid_negative_ts', 'make_zero',
#             '-err_detect', 'ignore_err',
#             '-rtsp_transport', 'tcp',
#             '-i', self.rtsp_url,
#             '-vf', f'fps=1/{VIDEO_CHUNK_INTERVAL}',
#             '-f', 'image2pipe',
#             '-vcodec', 'mjpeg',
#             '-q:v', '2',
#             '-'
#         ]

#         logging.info(f"Starting ffmpeg video with: {' '.join(command_video[:6])} ...")
#         proc = await asyncio.create_subprocess_exec(
#             *command_video,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE
#         )
#         self.ffmpeg_process = proc

#         stderr_task = asyncio.create_task(self._log_stderr(proc.stderr))

#         try:
#             frame_count = 0
#             while self.is_running:
#                 marker = await proc.stdout.read(2)
#                 if not marker or marker != b'\xff\xd8':
#                     if not marker:
#                         logging.warning("[STREAM] FFmpeg video stream ended (no more frames).")
#                         break
#                     continue

#                 frame_data = marker
#                 while self.is_running:
#                     chunk = await proc.stdout.read(1024)
#                     if not chunk:
#                         break
#                     frame_data += chunk
#                     if b'\xff\xd9' in chunk:
#                         end_pos = frame_data.rfind(b'\xff\xd9')
#                         frame_data = frame_data[:end_pos + 2]
#                         break

#                 if len(frame_data) > 2:
#                     frame_count += 1
#                     b64 = base64.b64encode(frame_data).decode()
#                     try:
#                         await asyncio.to_thread(self.conversation.append_video, b64)
#                         if frame_count % 10 == 0:
#                             logging.info(f"[STREAM] Sent video frame #{frame_count} ({len(frame_data)} bytes)")
#                     except Exception as e:
#                         logging.warning(f"[STREAM] append_video failed: {e}. Attempting reconnect.")
#                         await self.setup_qwen_connection(["audio", "video"])
#         except Exception as e:
#             logging.error(f"[STREAM] Error in AV video read loop: {e}", exc_info=True)
#         finally:
#             await stderr_task
#             logging.info(f"[STREAM] AV Video read loop finished. Total frames: {frame_count}")

# # ========== MAIN ENTRY ==========
# def main():
#     parser = argparse.ArgumentParser(description="Process RTSP stream with Qwen Omni API")
#     parser.add_argument("--rtsp-url", required=True, help="RTSP stream URL")
#     parser.add_argument("--focus", choices=["audio", "av"], default="audio", help="Processing focus")
#     args = parser.parse_args()

#     if args.focus == "audio":
#         processor = RTSPStreamProcessor(args.rtsp_url)
#     elif args.focus == "video":
#         processor = RTSPStreamProcessorAV(args.rtsp_url)
#     try:
#         asyncio.run(processor.run())
#     except KeyboardInterrupt:
#         logging.info("Stopped by user")
#     except Exception as e:
#         logging.error(f"Main runner error: {e}", exc_info=True)


# if __name__ == "__main__":
#     main()





# import os
# import json
# import asyncio
# import base64
# import logging
# from textwrap import dedent
# from dotenv import load_dotenv


# load_dotenv()
# apikey = os.getenv("DASHSCOPE_API_KEY")


# # Set to environment BEFORE importing SDK
# os.environ["DASHSCOPE_API_KEY"] = apikey

# from typing import Optional
# from dashscope.audio.qwen_omni import *
# from dashscope.audio.qwen_omni.omni_realtime import (
#     AudioFormat,
#     MultiModality,
#     OmniRealtimeConversation,
#     OmniRealtimeCallback,
# )
# from source.agents.base_processor import BaseStreamProcessor
# from source.agents.qwen_live_audio.prompt import PROMPTS

# SEND_SAMPLE_RATE = 16000
# MAX_RECONNECT_ATTEMPTS = 5
# INITIAL_RECONNECT_DELAY = 2.0
# MAX_RECONNECT_DELAY = 60.0


# class QwenCallback(OmniRealtimeCallback):
#     """Callback handler for Qwen Omni API events"""

#     def __init__(self, websocket=None, loop: Optional[asyncio.AbstractEventLoop] = None, reconnect_callback=None):
#         self.websocket = websocket
#         self.session_id = None
#         self.accumulated_text = ""
#         self.loop = loop or asyncio.get_event_loop()
#         self.reconnect_callback = reconnect_callback  # ✅ Callback untuk trigger reconnect

#     def on_open(self) -> None:
#         logging.info('✅ Qwen connection opened successfully')

#     def on_close(self, close_status_code, close_msg) -> None:
#         logging.warning(f'🔌 Qwen connection closed: {close_status_code} - {close_msg}')
        
#         # ✅ Trigger reconnect jika connection closed unexpectedly
#         if self.reconnect_callback and close_status_code != 1000:  # 1000 = normal close
#             logging.info('🔄 Scheduling reconnection...')
#             asyncio.run_coroutine_threadsafe(self.reconnect_callback(), self.loop)

#     def on_event(self, response: dict) -> None:
#         try:
#             event_type = response.get('type')
#             logging.info(f"📡 Qwen Event: {event_type}")

#             if event_type == 'session.created':
#                 self.session_id = response['session']['id']
#                 logging.info(f'✓ Session started: {self.session_id}')

#             elif event_type == 'conversation.item.input_audio_transcription.completed':
#                 transcript = response.get('transcript', '')
#                 logging.info(f'🎤 Transcription: {transcript}')

#             elif event_type == 'response.text.delta':
#                 text = response.get('delta', '')
#                 logging.info(f'📝 Text delta: {text}')
#                 self.accumulated_text += text

#             elif event_type == 'response.text.done':
#                 text = response.get('text', '')
#                 logging.info(f'✓ Full text response: {text}')
#                 self._try_send_alert(text)
#                 self.accumulated_text = ""

#             elif event_type == 'response.done':
#                 logging.info('✓ Response completed')
#                 if self.accumulated_text:
#                     self._try_send_alert(self.accumulated_text)
#                     self.accumulated_text = ""

#             elif event_type == 'input_audio_buffer.speech_started':
#                 logging.info('🔊 Speech detected in audio stream')

#             elif event_type == 'input_audio_buffer.speech_stopped':
#                 logging.info('🔇 Speech ended')

#             elif event_type == 'input_audio_buffer.committed':
#                 logging.info('✓ Audio buffer committed - waiting for response')

#             elif event_type == 'conversation.item.created':
#                 item = response.get('item', {})
#                 logging.info(f'💬 Conversation item created: {item.get("type")}')

#             elif event_type == 'response.created':
#                 logging.info('📄 Response generation started')

#             elif event_type == 'response.output_item.added':
#                 logging.info('➕ Output item added to response')

#             elif event_type == 'response.content_part.added':
#                 content_part = response.get('part', {})
#                 logging.info(f'📋 Content part added: {content_part.get("type")}')

#             else:
#                 logging.debug(f'ℹ️ Other event: {event_type}')

#         except Exception as e:
#             logging.error(f'❌ Error in callback: {e}', exc_info=True)

#     def _send_json_threadsafe(self, data: dict):
#         """Send websocket JSON safely from any thread."""
#         if not self.websocket:
#             return
#         try:
#             coro = self.websocket.send_json(data)
#             asyncio.run_coroutine_threadsafe(coro, self.loop)
#             logging.info(f'🚨 Alert sent (threadsafe): {data}')
#         except Exception as e:
#             logging.error(f'❌ Error sending alert threadsafe: {e}', exc_info=True)

#     def _try_send_alert(self, text: str):
#         """Try to parse and send alert via websocket"""
#         if not self.websocket or not text:
#             return

#         try:
#             data = json.loads(text.strip())
#             if isinstance(data, dict) and ('alert' in data or 'description' in data):
#                 self._send_json_threadsafe(data)
#                 return
#         except json.JSONDecodeError:
#             try:
#                 start_idx = text.find('{')
#                 end_idx = text.rfind('}')
#                 if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
#                     json_str = text[start_idx:end_idx+1]
#                     data = json.loads(json_str)
#                     if isinstance(data, dict) and ('alert' in data or 'description' in data):
#                         self._send_json_threadsafe(data)
#                         return
#             except Exception:
#                 logging.debug('Could not extract JSON from text', exc_info=False)
#         except Exception as e:
#             logging.error(f'❌ Unexpected error parsing alert text: {e}', exc_info=True)


# class QwenProcessor(BaseStreamProcessor):
#     def __init__(self, rtsp_url, websocket=None, focus="audio_video"):
#         super().__init__(rtsp_url, focus)
#         self.websocket = websocket
#         self.conversation = None
#         self.reconnect_attempts = 0
#         self.reconnect_delay = INITIAL_RECONNECT_DELAY
#         self.is_reconnecting = False

#     async def initialize_session(self):
#         """Initialize Qwen session with auto-reconnect support"""
#         logging.info("🔌 Connecting to Qwen Omni...")
        
#         # Get event loop for thread-safe callback
#         loop = asyncio.get_event_loop()
        
#         try:
#             self.conversation = OmniRealtimeConversation(
#                 model="qwen3-omni-flash-realtime",
#                 callback=QwenCallback(
#                     websocket=self.websocket, 
#                     loop=loop,
#                     reconnect_callback=self._handle_reconnect  # ✅ Pass reconnect handler
#                 ),
#                 url="wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
#             )
            
#             await asyncio.to_thread(self.conversation.connect)
            
#             await asyncio.to_thread(
#                 self.conversation.update_session,
#                 voice="Cherry",
#                 output_modalities=[MultiModality.TEXT],
#                 enable_turn_detection=False,
#                 input_audio_format=AudioFormat.PCM_16000HZ_MONO_16BIT,
#                 instructions=PROMPTS["agent_qwen"]
#             )
            
#             # ✅ Reset reconnect counters on successful connection
#             self.reconnect_attempts = 0
#             self.reconnect_delay = INITIAL_RECONNECT_DELAY
#             self.is_reconnecting = False
            
#             logging.info("✅ Qwen session initialized successfully")
            
#         except Exception as e:
#             logging.error(f"❌ Failed to initialize Qwen session: {e}", exc_info=True)
            
#             # ✅ Auto-reconnect on failure
#             if self.running and self.reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
#                 await self._handle_reconnect()
#             else:
#                 raise

#     async def _handle_reconnect(self):
#         """Handle reconnection with exponential backoff"""
#         if self.is_reconnecting:
#             logging.debug("⏳ Reconnection already in progress, skipping...")
#             return
        
#         if not self.running:
#             logging.info("🛑 Processor stopped, aborting reconnection")
#             return
        
#         if self.reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
#             logging.error(f"❌ Max reconnection attempts ({MAX_RECONNECT_ATTEMPTS}) reached. Giving up.")
#             self.running = False
#             return
        
#         self.is_reconnecting = True
#         self.reconnect_attempts += 1
        
#         logging.warning(f"🔄 Reconnection attempt {self.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS} in {self.reconnect_delay}s...")
        
#         await asyncio.sleep(self.reconnect_delay)
        
#         try:
#             # ✅ Close old connection if exists
#             if self.conversation:
#                 try:
#                     await asyncio.to_thread(self.conversation.close)
#                 except Exception as e:
#                     logging.debug(f"Error closing old connection: {e}")
            
#             # ✅ Reinitialize session
#             await self.initialize_session()
            
#             logging.info("✅ Reconnection successful!")
            
#         except Exception as e:
#             logging.error(f"❌ Reconnection failed: {e}", exc_info=True)
            
#             # ✅ Exponential backoff
#             self.reconnect_delay = min(self.reconnect_delay * 2, MAX_RECONNECT_DELAY)
#             self.is_reconnecting = False
            
#             # ✅ Schedule next retry
#             if self.running and self.reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
#                 await self._handle_reconnect()

#     async def send_realtime_data(self, audio_chunk=None, video_frame=None):
#         """Send data with error handling"""
#         if not self.conversation:
#             logging.warning("⚠️ Cannot send data: conversation not initialized")
#             return
        
#         try:
#             if audio_chunk:
#                 await asyncio.to_thread(self.conversation.append_audio, audio_chunk)
#             if video_frame:
#                 await asyncio.to_thread(self.conversation.append_video, video_frame)
#         except Exception as e:
#             logging.error(f"❌ Error sending realtime data: {e}", exc_info=True)
            
#             # ✅ Trigger reconnect on send failure
#             if self.running:
#                 await self._handle_reconnect()

#     async def receive_responses(self):
#         """Responses are handled by the callback."""
#         while self.running:
#             await asyncio.sleep(1.0)

#     async def send_text_message(self, text: str):
#         """Send manual text input to the model."""
#         try:
#             if self.websocket:
#                 await self.websocket.send_json({"type": "response", "text": text})
            
#             if self.conversation:
#                 await asyncio.to_thread(self.conversation.append_text, text)
#         except Exception as e:
#             logging.error(f"❌ Error sending text message: {e}", exc_info=True)

#     async def cleanup_session(self):
#         """Clean shutdown"""
#         self.running = False  
        
#         try:
#             if self.conversation:
#                 await asyncio.to_thread(self.conversation.close)
#                 logging.info("🧹 Qwen session closed successfully")
#             else:
#                 logging.warning("⚠️ No active Qwen session to close")
#         except Exception as e:
#             logging.error(f"❌ Error closing Qwen session: {e}", exc_info=True)



# # ─────────────────────────────────────────────
# # Gemini Processor Class
# # ─────────────────────────────────────────────
# class GeminiProcessor(BaseStreamProcessor):
#     """Gemini Live API processor with audio/video streaming support."""

#     async def initialize_session(self):
#         """Initialize Gemini Live session."""
#         logger.info("🟢 Initializing Gemini Live session...")
#         try:
#             self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
#             self.session = self.client.realtime.connect(model=MODEL, config=CONFIG)
#             logger.info(f"✅ Gemini session initialized with model: {MODEL}")
#         except Exception as e:
#             logger.error(f"❌ Failed to initialize Gemini session: {e}")
#             raise

#     async def send_realtime_data(self):
#         """Send audio/video chunks to Gemini in real-time."""
#         logger.info("🎧 Starting realtime data stream to Gemini...")
#         try:
#             while self.is_running:
#                 item = await self.queue.get()
#                 if item["type"] == "audio":
#                     chunk = item["data"]
#                     # Potong sesuai AUDIO_CHUNK_SIZE untuk kestabilan stream
#                     for i in range(0, len(chunk), AUDIO_CHUNK_SIZE):
#                         segment = chunk[i:i + AUDIO_CHUNK_SIZE]
#                         await asyncio.to_thread(
#                             self.session.send,
#                             {
#                                 "type": "input_audio_buffer.append",
#                                 "audio": base64.b64encode(segment).decode("utf-8"),
#                                 "sample_rate": SEND_SAMPLE_RATE,
#                             },
#                         )
#                 elif item["type"] == "video":
#                     frame_b64 = item["data"]
#                     await asyncio.to_thread(
#                         self.session.send,
#                         {
#                             "type": "input_image",
#                             "data": frame_b64,
#                             "mime_type": "image/jpeg",
#                         },
#                     )

#         except Exception as e:
#             logger.error(f"❌ Error sending data to Gemini: {e}")

#     async def receive_responses(self):
#         """Listen and forward Gemini responses."""
#         logger.info("📡 Listening for Gemini responses...")
#         try:
#             async for event in self.session:
#                 if event["type"] == "response.text.delta":
#                     text = event.get("delta", "").strip()
#                     if text:
#                         logger.info(f"🤖 Gemini: {text}")
#                         if self.websocket:
#                             await self.websocket.send(
#                                 json.dumps({"alert": "info", "text": text})
#                             )
#                 elif event["type"] == "response.completed":
#                     logger.debug("✅ Gemini response completed.")
#         except Exception as e:
#             logger.error(f"❌ Error receiving from Gemini: {e}")

#     async def send_text_message(self, text: str):
#         """Send manual text messages to Gemini."""
#         try:
#             await asyncio.to_thread(
#                 self.session.send,
#                 {"type": "input_text", "text": text},
#             )
#             logger.info(f"💬 Sent text message to Gemini: {text}")
#         except Exception as e:
#             logger.error(f"❌ Error sending text message: {e}")

#     async def cleanup_session(self):
#         """Safely close the Gemini session."""
#         try:
#             if self.session:
#                 await asyncio.to_thread(self.session.close)
#             logger.info("🧹 Gemini session closed cleanly.")
#         except Exception as e:
#             logger.error(f"❌ Error during Gemini cleanup: {e}")



#################

