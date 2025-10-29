# -*- coding: utf-8 -*-
"""
Base Stream Processor - Extracts common RTSP streaming patterns
"""

import asyncio
import base64
import io
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Literal
import cv2
import PIL.Image
from loguru import logger


class BaseStreamProcessor(ABC):
    """
    Abstract base class for processing RTSP streams and sending to LLM APIs.
    
    Handles common functionality:
    - RTSP audio/video capture
    - Media encoding (JPEG, PCM)
    - Queue-based data pipeline
    - Async task orchestration
    
    Subclasses must implement API-specific communication.
    """
    
    # Constants that can be overridden by subclasses
    SEND_SAMPLE_RATE = 16000
    AUDIO_CHUNK_SIZE = 2048
    VIDEO_INTERVAL = 1.0  # seconds between frames
    MAX_QUEUE_SIZE = 100
    IMAGE_MAX_SIZE = (1024, 1024)
    
    def __init__(
        self,
        rtsp_url: str,
        focus: Literal["audio_video", "audio_only", "video_only"] = "audio_video"
    ):
        self.rtsp_url = rtsp_url
        self.focus = focus
        self.out_queue: Optional[asyncio.Queue] = None
        self.session = None
        
    # ----------------------
    # Media Capture Methods (Common)
    # ----------------------
    
    async def capture_video_frames(self):
        """Capture video frames from RTSP and enqueue them."""
        logger.info("Starting video capture...")
        cap = None
        try:
            cap = await asyncio.to_thread(cv2.VideoCapture, self.rtsp_url)
            if not cap.isOpened():
                logger.error(f"Cannot open RTSP video stream: {self.rtsp_url}")
                return
                
            while cap.isOpened():
                ret, frame = await asyncio.to_thread(cap.read)
                if not ret:
                    logger.warning("Video stream ended or frame read failed.")
                    break
                    
                # Encode frame
                payload = await self._encode_frame(frame)
                await self.out_queue.put(payload)
                await asyncio.sleep(self.VIDEO_INTERVAL)
                
        finally:
            if cap and cap.isOpened():
                cap.release()
            logger.info("Video capture finished.")
    
    async def _encode_frame(self, frame) -> Dict[str, str]:
        """Convert OpenCV frame to encoded format."""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)
        img.thumbnail(self.IMAGE_MAX_SIZE)
        
        buf = io.BytesIO()
        img.save(buf, format="jpeg")
        buf.seek(0)
        
        return {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(buf.read()).decode('utf-8')
        }
    
    async def capture_audio_stream(self):
        """Extract audio from RTSP using FFmpeg and enqueue PCM chunks."""
        logger.info("Starting audio capture...")
        command = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-fflags', '+igndts+genpts',
            '-i', self.rtsp_url,
            '-loglevel', 'error',
            '-nostats', '-hide_banner',
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ar', str(self.SEND_SAMPLE_RATE),
            '-ac', '1',
            '-'
        ]
        
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            error_task = asyncio.create_task(self._log_ffmpeg_stderr(proc.stderr))
            
            while True:
                audio_data = await proc.stdout.read(self.AUDIO_CHUNK_SIZE)
                if not audio_data:
                    break
                await self.out_queue.put({
                    "data": audio_data,
                    "mime_type": "audio/pcm"
                })
            
            return_code = await proc.wait()
            await error_task
            
            if return_code != 0:
                logger.error(f"FFmpeg exited with code {return_code}")
            else:
                logger.info("Audio stream ended successfully.")
                
        except FileNotFoundError:
            logger.error("FFmpeg not found. Install and add to PATH.")
        finally:
            if proc and proc.returncode is None:
                proc.terminate()
                await proc.wait()
            logger.info("Audio capture finished.")
    
    async def _log_ffmpeg_stderr(self, stderr):
        """Log FFmpeg errors."""
        while True:
            line = await stderr.readline()
            if not line:
                break
            logger.error(f"FFmpeg Error: {line.decode().strip()}")
    
    # ----------------------
    # User Input (Common)
    # ----------------------
    
    async def handle_text_input(self):
        """Asynchronously read user input and send to API."""
        logger.info("Text input task started. Type 'q' to quit.")
        while True:
            try:
                message = await asyncio.to_thread(input, "\nmessage > ")
                if message.lower() == "q":
                    logger.info("Quit command received. Shutting down.")
                    break
                await self.send_text_message(message or ".")
            except (BrokenPipeError, IOError):
                logger.warning("Input stream closed.")
                break
    
    # ----------------------
    # Abstract Methods (API-Specific)
    # ----------------------
    
    @abstractmethod
    async def initialize_session(self):
        """Initialize API session. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def send_realtime_data(self):
        """Send media from queue to API. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def receive_responses(self):
        """Receive and display API responses. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def send_text_message(self, message: str):
        """Send text message to API. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def cleanup_session(self):
        """Clean up API session. Must be implemented by subclasses."""
        pass
    
    # ----------------------
    # Main Orchestration
    # ----------------------
    
    async def run(self):
        """Run all tasks concurrently."""
        try:
            await self.initialize_session()
            self.out_queue = asyncio.Queue(maxsize=self.MAX_QUEUE_SIZE)
            
            async with asyncio.TaskGroup() as tg:
                logger.info("Stream processor started.")
                
                # User input
                text_input_task = tg.create_task(self.handle_text_input())
                
                # API communication
                tg.create_task(self.send_realtime_data())
                tg.create_task(self.receive_responses())
                
                # Media capture based on focus
                if self.focus in ["audio_video", "audio_only"]:
                    logger.info("Audio processing enabled.")
                    tg.create_task(self.capture_audio_stream())
                
                if self.focus in ["audio_video", "video_only"]:
                    logger.info("Video processing enabled.")
                    tg.create_task(self.capture_video_frames())
                
                # Wait for user to quit
                await text_input_task
                raise asyncio.CancelledError("User requested exit.")
                
        except asyncio.CancelledError:
            logger.info("Shutting down application.")
        except Exception as e:
            logger.exception("Unexpected error in main loop")
        finally:
            # CRITICAL: Always cleanup, even if errors occur
            logger.info("Cleaning up session...")
            await self.cleanup_session()
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return processor metadata."""
        return {
            "rtsp_url": self.rtsp_url,
            "focus": self.focus,
            "sample_rate": self.SEND_SAMPLE_RATE,
            "audio_chunk_size": self.AUDIO_CHUNK_SIZE
        }