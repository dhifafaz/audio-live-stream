# -*- coding: utf-8 -*-
"""
Qwen RTSP Stream Processor - Implements Qwen Omni-specific API communication
"""

import os
import asyncio
import base64
import logging
import json
import traceback
from textwrap import dedent
from typing import Optional
from dashscope.audio.qwen_omni import (
    OmniRealtimeCallback,
    OmniRealtimeConversation,
    MultiModality,
    AudioFormat
)
import dashscope
from loguru import logger
from dotenv import load_dotenv

from source.agents.base_processor import BaseStreamProcessor
from source.agents.qwen_live_audio.prompt import PROMPTS

load_dotenv()

# Set DashScope API key
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY", "sk")


class QwenCallback(OmniRealtimeCallback):
    """Callback handler for Qwen Omni API events"""
    
    def __init__(self, websocket=None):
        self.websocket = websocket
        self.session_id = None
        self.accumulated_text = ""
        
    def on_open(self) -> None:
        logger.info('✅ Qwen connection opened successfully')
    
    def on_close(self, close_status_code, close_msg) -> None:
        logger.info(f'Qwen connection closed: {close_status_code} - {close_msg}')
    
    def on_event(self, response: dict) -> None:
        try:
            event_type = response.get('type')
            logger.debug(f"Qwen Event: {event_type}")
            
            if event_type == 'session.created':
                self.session_id = response['session']['id']
                logger.info(f'✓ Session started: {self.session_id}')
            
            elif event_type == 'conversation.item.input_audio_transcription.completed':
                transcript = response.get('transcript', '')
                logger.info(f'🎤 Transcription: {transcript}')
            
            elif event_type == 'response.text.delta':
                text = response.get('delta', '')
                self.accumulated_text += text
                print(text, end="", flush=True)
                
            elif event_type == 'response.text.done':
                text = response.get('text', '')
                logger.info(f'✓ Full text response: {text}')
                self._try_send_alert(text)
                self.accumulated_text = ""
                print()  # New line after complete response
                
            elif event_type == 'response.done':
                logger.info('✓ Response completed')
                if self.accumulated_text:
                    self._try_send_alert(self.accumulated_text)
                    self.accumulated_text = ""
                
            elif event_type == 'input_audio_buffer.speech_started':
                logger.info('🔊 Speech detected in audio stream')
                
            elif event_type == 'input_audio_buffer.speech_stopped':
                logger.info('🔇 Speech ended')
                
            elif event_type == 'input_audio_buffer.committed':
                logger.debug('✓ Audio buffer committed - waiting for response')
                
            elif event_type == 'conversation.item.created':
                item = response.get('item', {})
                logger.debug(f'💬 Conversation item created: {item.get("type")}')
                
            elif event_type == 'response.created':
                logger.debug('📄 Response generation started')
                
            elif event_type == 'response.output_item.added':
                logger.debug('➕ Output item added to response')
                
            elif event_type == 'response.content_part.added':
                content_part = response.get('part', {})
                logger.debug(f'📋 Content part added: {content_part.get("type")}')
                
            else:
                logger.debug(f'ℹ️ Other event: {event_type}')
                
        except Exception as e:
            logger.error(f'Error in callback: {e}')
            traceback.print_exc()
    
    def _try_send_alert(self, text: str):
        """Try to parse and send alert via websocket"""
        if not self.websocket or not text:
            return
        
        try:
            # Try to parse as JSON
            data = json.loads(text.strip())
            if 'alert' in data:
                if self.websocket:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.websocket.send_json(data))
                    loop.close()
                logger.info(f'🚨 Alert sent: {data}')
        except json.JSONDecodeError:
            # Try to extract JSON from text
            try:
                start_idx = text.find('{')
                end_idx = text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = text[start_idx:end_idx+1]
                    data = json.loads(json_str)
                    if 'alert' in data:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.websocket.send_json(data))
                        loop.close()
                        logger.info(f'🚨 Alert sent (extracted): {data}')
            except:
                logger.debug(f'Could not parse as JSON: {text[:100]}...')
        except Exception as e:
            logger.error(f'Error sending alert: {e}')


class QwenStreamProcessor(BaseStreamProcessor):
    """
    Qwen-specific implementation of RTSP stream processor.
    Handles Qwen Omni API communication with buffered audio processing.
    """
    
    # Qwen-specific constants
    AUDIO_CHUNK_SIZE = 3200  # Qwen expects 3200 bytes chunks (100ms at 16kHz)
    MODEL = 'qwen3-omni-flash-realtime'
    WS_URL = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
    
    def __init__(
        self,
        rtsp_url: str,
        focus: str = "audio_video",
        websocket=None,
        audio_buffer_duration: float = 5.0
    ):
        super().__init__(rtsp_url, focus)
        
        self.websocket = websocket
        self.conversation: Optional[OmniRealtimeConversation] = None
        self.callback = QwenCallback(websocket)
        self.audio_buffer_duration = audio_buffer_duration
        
        # Calculate chunks per buffer for commit/response cycle
        self.chunks_per_buffer = int(
            self.audio_buffer_duration * self.SEND_SAMPLE_RATE * 2 / self.AUDIO_CHUNK_SIZE
        )
        
        logger.info("✅ Qwen stream processor initialized")
        logger.info(f"Buffer duration: {audio_buffer_duration}s ({self.chunks_per_buffer} chunks)")
    
    async def initialize_session(self):
        """Initialize Qwen Omni API connection and session"""
        logger.info('Initializing Qwen Omni connection...')
        
        # Create conversation instance
        self.conversation = OmniRealtimeConversation(
            model=self.MODEL,
            callback=self.callback,
            url=self.WS_URL
        )
        
        # Connect to WebSocket
        await asyncio.to_thread(self.conversation.connect)
        
        # Configure session
        await asyncio.to_thread(
            self.conversation.update_session,
            voice='Cherry',
            output_modalities=[MultiModality.TEXT],
            input_audio_format=AudioFormat.PCM_16000HZ_MONO_16BIT,
            enable_input_audio_transcription=True,
            input_audio_transcription_model='gummy-realtime-v1',
            enable_turn_detection=False,  # Manual commit/response control
            instructions=dedent(PROMPTS['agent_qwen']),
        )
        
        logger.info('✅ Qwen Omni connection established and configured')
        
        if self.websocket:
            await self.websocket.send_json({
                "type": "status",
                "message": "Qwen connection established"
            })
    
    async def send_realtime_data(self):
        """
        Send media from queue to Qwen API with buffered audio processing.
        
        Qwen requires a commit/response cycle:
        1. Append audio chunks to buffer
        2. After N chunks, commit the buffer
        3. Request a response
        """
        logger.info("Realtime media sending started (Qwen buffered mode)")
        
        chunk_count = 0
        buffer_chunk_count = 0
        
        while True:
            try:
                payload = await self.out_queue.get()
                mime_type = payload.get("mime_type")
                
                # Handle audio
                if mime_type == "audio/pcm":
                    audio_data = payload["data"]
                    audio_b64 = base64.b64encode(audio_data).decode('ascii')
                    
                    # Check connection
                    if not (self.conversation and 
                           hasattr(self.conversation, 'ws') and 
                           self.conversation.ws):
                        logger.error("Qwen conversation connection lost")
                        break
                    
                    # Append audio to Qwen buffer
                    await asyncio.to_thread(self.conversation.append_audio, audio_b64)
                    
                    chunk_count += 1
                    buffer_chunk_count += 1
                    
                    # Log progress
                    if chunk_count % 50 == 0:
                        logger.info(f"Sent {chunk_count} audio chunks")
                    
                    # Commit buffer and request response after N chunks
                    if buffer_chunk_count >= self.chunks_per_buffer:
                        logger.info(
                            f"💾 Committing {self.audio_buffer_duration}s of audio "
                            f"and requesting response..."
                        )
                        
                        await asyncio.to_thread(self.conversation.commit)
                        await asyncio.to_thread(self.conversation.create_response)
                        
                        buffer_chunk_count = 0
                        await asyncio.sleep(0.5)  # Brief pause between cycles
                
                # Handle video frames
                elif mime_type == "image/jpeg":
                    # Qwen Omni primarily processes audio; video could be logged or skipped
                    # If you want to send images, implement Qwen's image handling here
                    logger.debug("Video frame received (Qwen audio-only mode)")
                
                self.out_queue.task_done()
                
            except Exception as e:
                if "Connection is already closed" in str(e):
                    logger.error("Connection closed, stopping data sending")
                    break
                logger.error(f"Error sending data to Qwen: {e}")
                continue
        
        # Commit any remaining audio in buffer
        if buffer_chunk_count > 0:
            logger.info("Committing final audio buffer...")
            try:
                await asyncio.to_thread(self.conversation.commit)
                await asyncio.to_thread(self.conversation.create_response)
            except Exception as e:
                logger.error(f"Error committing final buffer: {e}")
        
        logger.info(f"Realtime sending finished. Total chunks: {chunk_count}")
    
    async def receive_responses(self):
        """
        Receive text responses from Qwen API.
        
        Note: Qwen uses callback-based event system, so responses are handled
        in QwenCallback.on_event(). This method can be used for additional
        response processing if needed.
        """
        logger.info("Response listener started (callback-based)")
        
        # Qwen responses are handled via callbacks
        # Keep this task alive to maintain the async task group
        try:
            while True:
                await asyncio.sleep(1)
                
                # Optional: Check connection health
                if not (self.conversation and 
                       hasattr(self.conversation, 'ws') and 
                       self.conversation.ws):
                    logger.warning("Qwen connection lost in receive loop")
                    break
                    
        except asyncio.CancelledError:
            logger.info("Response listener cancelled")
    
    async def send_text_message(self, message: str):
        """Send text message to Qwen API (not used in audio-only mode)"""
        # Qwen Omni in this configuration is audio-focused
        # Text input could be implemented if Qwen supports text in this mode
        logger.debug(f"Text message (not sent to Qwen audio API): {message}")
    
    async def cleanup_session(self):
        """Clean up Qwen session"""
        logger.info("Cleaning up Qwen session...")
        
        if self.conversation:
            try:
                await asyncio.to_thread(self.conversation.close)
                logger.info("✅ Qwen conversation closed")
            except Exception as e:
                logger.error(f"Error closing Qwen conversation: {e}")
        
        if self.websocket:
            try:
                await self.websocket.send_json({
                    "type": "status",
                    "message": "Connection closed"
                })
            except Exception as e:
                logger.error(f"Error sending websocket status: {e}")
    
    async def handle_text_input(self):
        """
        Override text input for Qwen audio-only mode.
        Qwen Omni in this configuration doesn't support text input during audio streaming.
        """
        logger.info("Text input disabled (Qwen audio-only mode). Type 'q' to quit.")
        
        while True:
            try:
                message = await asyncio.to_thread(input, "\ncommand > ")
                if message.lower() == "q":
                    logger.info("Quit command received. Shutting down.")
                    break
                else:
                    logger.warning("Text input not supported in Qwen audio mode")
                    
            except (BrokenPipeError, IOError):
                logger.warning("Input stream closed.")
                break
    
    def get_metadata(self):
        """Return Qwen-specific metadata"""
        base_metadata = super().get_metadata()
        return {
            **base_metadata,
            "provider": "Qwen",
            "model": self.MODEL,
            "audio_buffer_duration": self.audio_buffer_duration,
            "chunks_per_buffer": self.chunks_per_buffer,
            "audio_chunk_size": self.AUDIO_CHUNK_SIZE
        }


def main():
    """Main entry point with CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Process RTSP stream with Qwen Omni API (Audio-focused)"
    )
    parser.add_argument(
        "--rtsp-url",
        type=str,
        required=True,
        help="RTSP URL of the stream"
    )
    parser.add_argument(
        "--focus",
        type=str,
        default="audio_only",  # Qwen Omni is optimized for audio
        choices=["audio_video", "audio_only", "video_only"],
        help="Processing focus (audio_only recommended for Qwen)"
    )
    parser.add_argument(
        "--buffer-duration",
        type=float,
        default=5.0,
        help="Audio buffer duration in seconds before commit/response (default: 5.0)"
    )
    
    args = parser.parse_args()
    
    # Warn if not using audio_only
    if args.focus != "audio_only":
        logger.warning(
            "⚠️  Qwen Omni is optimized for audio processing. "
            "Consider using --focus audio_only"
        )
    
    processor = QwenStreamProcessor(
        rtsp_url=args.rtsp_url,
        focus=args.focus,
        audio_buffer_duration=args.buffer_duration
    )
    
    try:
        asyncio.run(processor.run())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting.")


if __name__ == "__main__":
    main()