

# import sys
# import asyncio
# import base64
# import subprocess
# import logging
# import argparse
# import json
# import traceback
# from .prompt import PROMPTS
# from textwrap import dedent

# from dashscope.audio.qwen_omni import *
# import dashscope

# # Set up logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# # Configuration
# SEND_SAMPLE_RATE = 16000
# AUDIO_CHUNK_SIZE = 3200  # Qwen expects 3200 bytes chunks at 16kHz (100ms of audio)

# # Set your DashScope API key
# dashscope.api_key = 'sk'


# class QwenCallback(OmniRealtimeCallback):
#     """Callback handler for Qwen Omni API events"""
    
#     def __init__(self, websocket=None):
#         self.websocket = websocket
#         self.session_id = None
#         self.accumulated_text = ""
        
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
#             logging.error(f'Error in callback: {e}')
#             traceback.print_exc()
    
#     def _try_send_alert(self, text: str):
#         """Try to parse and send alert via websocket"""
#         if not self.websocket or not text:
#             return
        
#         try:
#             data = json.loads(text.strip())
#             if 'alert' in data:
#                 if self.websocket:
#                     loop = asyncio.new_event_loop()
#                     asyncio.set_event_loop(loop)
#                     loop.run_until_complete(self.websocket.send_json(data))
#                     loop.close()
#                 logging.info(f'🚨 Alert sent: {data}')
#         except json.JSONDecodeError:
#             try:
#                 start_idx = text.find('{')
#                 end_idx = text.rfind('}')
#                 if start_idx != -1 and end_idx != -1:
#                     json_str = text[start_idx:end_idx+1]
#                     data = json.loads(json_str)
#                     if 'alert' in data:
#                         loop = asyncio.new_event_loop()
#                         asyncio.set_event_loop(loop)
#                         loop.run_until_complete(self.websocket.send_json(data))
#                         loop.close()
#                         logging.info(f'🚨 Alert sent (extracted): {data}')
#             except:
#                 logging.debug(f'Could not parse as JSON: {text[:100]}...')
#         except Exception as e:
#             logging.error(f'Error sending alert: {e}')


# class RTSPStreamProcessor:
#     """Processes RTSP stream and sends audio to Qwen Omni API"""
    
#     def __init__(self, rtsp_url: str, websocket=None):
#         self.rtsp_url = rtsp_url
#         self.websocket = websocket
#         self.conversation = None
#         self.callback = QwenCallback(websocket)
#         self.is_running = False
#         self.audio_buffer_duration = 5
#         self.chunks_per_buffer = int(self.audio_buffer_duration * SEND_SAMPLE_RATE * 2 / AUDIO_CHUNK_SIZE)
#         self.ffmpeg_process = None
        
#     async def setup_qwen_connection(self):
#         """Initialize connection to Qwen Omni API"""
#         logging.info('Initializing Qwen Omni connection...')
        
#         self.conversation = OmniRealtimeConversation(
#             model='qwen3-omni-flash-realtime',
#             callback=self.callback,
#             url="wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
#         )
        
#         await asyncio.to_thread(self.conversation.connect)
        
#         await asyncio.to_thread(
#             self.conversation.update_session,
#             voice='Cherry',
#             output_modalities=[MultiModality.TEXT],
#             input_audio_format=AudioFormat.PCM_16000HZ_MONO_16BIT,
#             enable_input_audio_transcription=True,
#             input_audio_transcription_model='gummy-realtime-v1',
#             enable_turn_detection=False,
#             instructions=dedent(PROMPTS['agent_qwen']),
#         )
        
#         logging.info('Qwen Omni connection established and configured')
    
#     async def listen_rtsp_audio(self):
#         """Extract audio from RTSP stream using FFmpeg and process in chunks"""
#         logging.info("Starting audio stream capture with FFmpeg...")
        
#         command = [
#             'ffmpeg',
#             '-rtsp_transport', 'tcp',
#             '-fflags', '+genpts+igndts+discardcorrupt',
#             '-use_wallclock_as_timestamps', '1',
#             '-max_interleave_delta', '0',
#             '-i', self.rtsp_url,
#             '-loglevel', 'fatal',
#             '-nostats', '-hide_banner',
#             '-f', 's16le',
#             '-acodec', 'pcm_s16le',
#             '-ar', str(SEND_SAMPLE_RATE),
#             '-ac', '1',
#             '-avoid_negative_ts', 'make_zero',
#             '-max_delay', '500000',
#             '-reorder_queue_size', '0',
#             '-'
#         ]
        
#         chunk_count = 0
#         buffer_chunk_count = 0
        
#         try:
#             self.ffmpeg_process = await asyncio.create_subprocess_exec(
#                 *command,
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.PIPE
#             )
            
#             error_task = asyncio.create_task(self._log_stderr(self.ffmpeg_process.stderr))
            
#             if self.websocket:
#                 await self.websocket.send_json({
#                     "type": "status",
#                     "message": "Audio stream connected, analyzing..."
#                 })
            
#             logging.info("FFmpeg process started, waiting for audio data...")
#             logging.info(f"Expected chunk size: {AUDIO_CHUNK_SIZE} bytes")
#             logging.info(f"Will commit and request response every {self.audio_buffer_duration} seconds ({self.chunks_per_buffer} chunks)")
            
#             while self.is_running:
#                 try:
#                     audio_data = await asyncio.wait_for(
#                         self.ffmpeg_process.stdout.read(AUDIO_CHUNK_SIZE),
#                         timeout=1.0
#                     )
                    
#                     if not audio_data:
#                         logging.warning("No more audio data from FFmpeg")
#                         break
                    
#                     chunk_count += 1
#                     buffer_chunk_count += 1
                    
#                     if chunk_count % 50 == 0:
#                         logging.info(f"Sent {chunk_count} audio chunks ({len(audio_data)} bytes each)")
                    
#                     audio_b64 = base64.b64encode(audio_data).decode('ascii')
                    
#                     if self.conversation and hasattr(self.conversation, 'ws') and self.conversation.ws:
#                         await asyncio.to_thread(self.conversation.append_audio, audio_b64)
#                     else:
#                         logging.error("Qwen conversation connection lost")
#                         break
                    
#                     if buffer_chunk_count >= self.chunks_per_buffer:
#                         logging.info(f"💾 Committing {self.audio_buffer_duration}s of audio and requesting response...")
                        
#                         await asyncio.to_thread(self.conversation.commit)
#                         await asyncio.to_thread(self.conversation.create_response)
                        
#                         buffer_chunk_count = 0
#                         await asyncio.sleep(0.5)
                        
#                 except asyncio.TimeoutError:
#                     if not self.is_running:
#                         break
#                     continue
#                 except Exception as e:
#                     if not self.is_running:
#                         break
#                     logging.error(f"Error processing audio chunk: {e}")
#                     if "Connection is already closed" in str(e):
#                         logging.error("Connection closed, stopping audio stream")
#                         break
#                     continue
            
#             if buffer_chunk_count > 0:
#                 logging.info("Committing final audio buffer...")
#                 try:
#                     await asyncio.to_thread(self.conversation.commit)
#                     await asyncio.to_thread(self.conversation.create_response)
#                 except:
#                     pass
            
#             error_task.cancel()
#             logging.info(f"Audio capture finished. Total chunks sent: {chunk_count}")
            
#         except FileNotFoundError:
#             logging.error("FFmpeg not found. Please install FFmpeg.")
#             if self.websocket:
#                 await self.websocket.send_json({
#                     "type": "error",
#                     "message": "FFmpeg not found"
#                 })
#         except Exception as e:
#             logging.error(f"Audio stream error: {e}")
#             traceback.print_exc()
#             if self.websocket:
#                 await self.websocket.send_json({
#                     "type": "error",
#                     "message": str(e)
#                 })
#         finally:
#             await self.cleanup_ffmpeg()
#             logging.info("Audio stream capture finished")
    
#     async def cleanup_ffmpeg(self):
#         """Clean up FFmpeg process"""
#         if self.ffmpeg_process and self.ffmpeg_process.returncode is None:
#             try:
#                 self.ffmpeg_process.terminate()
#                 await asyncio.wait_for(self.ffmpeg_process.wait(), timeout=3.0)
#             except asyncio.TimeoutError:
#                 self.ffmpeg_process.kill()
#                 await self.ffmpeg_process.wait()
#             except Exception as e:
#                 logging.error(f"Error cleaning up FFmpeg: {e}")
    
#     async def _log_stderr(self, stderr):
#         """Log FFmpeg errors"""
#         try:
#             while True:
#                 line = await stderr.readline()
#                 if not line:
#                     break
#                 logging.error(f"FFmpeg: {line.decode().strip()}")
#         except asyncio.CancelledError:
#             pass
    
#     async def stop(self):
#         """Stop the processor gracefully"""
#         logging.info("Stopping processor...")
#         self.is_running = False
        
#         await self.cleanup_ffmpeg()
        
#         if self.conversation:
#             try:
#                 await asyncio.to_thread(self.conversation.close)
#                 logging.info("Qwen conversation closed")
#             except Exception as e:
#                 logging.error(f"Error closing Qwen conversation: {e}")
    
#     async def run(self):
#         """Main run method"""
#         try:
#             self.is_running = True
            
#             await self.setup_qwen_connection()
#             await self.listen_rtsp_audio()
            
#         except Exception as e:
#             logging.error(f"Error in run: {e}")
#             if self.websocket:
#                 await self.websocket.send_json({
#                     "type": "error",
#                     "message": str(e)
#                 })
#         finally:
#             await self.stop()
#             logging.info("Processor stopped")


# def main():
#     """Main entry point for standalone usage"""
#     parser = argparse.ArgumentParser(description="Process RTSP stream with Qwen Omni API")
#     parser.add_argument(
#         "--rtsp-url",
#         type=str,
#         required=True,
#         help="RTSP URL of the stream"
#     )
#     args = parser.parse_args()
    
#     processor = RTSPStreamProcessor(rtsp_url=args.rtsp_url)
    
#     try:
#         asyncio.run(processor.run())
#     except KeyboardInterrupt:
#         logging.info("Stopped by user")


# if __name__ == "__main__":
#     main()



