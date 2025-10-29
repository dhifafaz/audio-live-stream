# -*- coding: utf-8 -*-
"""
Gemini RTSP Stream Processor - Implements Gemini-specific API communication
"""

import os
import asyncio
from textwrap import dedent
from google import genai
from loguru import logger
from dotenv import load_dotenv
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from source.agents.base_processor import BaseStreamProcessor
from source.agents.gemini_live_audio.prompt import PROMPTS

load_dotenv()


class GeminiStreamProcessor(BaseStreamProcessor):
    """
    Gemini-specific implementation of RTSP stream processor.
    Handles Gemini Live API communication.
    """
    
    MODEL = "models/gemini-2.0-flash-live-001"
    
    def __init__(self, rtsp_url: str, focus: str = "audio_video"):
        super().__init__(rtsp_url, focus)
        
        # Initialize Gemini client
        try:
            self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
            logger.info("✅ Gemini client initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini Client: {e}")
            raise
        
        self.config = {
            "response_modalities": ["TEXT"],
            "system_instruction": dedent(PROMPTS['agent_gemini'])
        }
        
        # Store context manager separately
        self.session_context = None
    
    async def initialize_session(self):
        """Initialize Gemini Live API session."""
        # Store BOTH the context manager AND the session
        self.session_context = self.client.aio.live.connect(
            model=self.MODEL,
            config=self.config
        )
        self.session = await self.session_context.__aenter__()
        logger.info("Connected to Gemini Live API.")
    
    async def send_realtime_data(self):
        """Send media from queue to Gemini API."""
        logger.info("Realtime media sending started.")
        try:
            while True:
                payload = await self.out_queue.get()
                await self.session.send(input=payload)
                self.out_queue.task_done()
        except asyncio.CancelledError:
            logger.info("Realtime data sender cancelled")
            raise
        except Exception as e:
            logger.error(f"Error sending realtime data: {e}")
            raise
    
    async def receive_responses(self):
        """Receive text responses from Gemini API and print to console."""
        logger.info("Response listener started.")
        try:
            while True:
                turn = self.session.receive()
                printed_prefix = False
                async for response in turn:
                    if text := response.text:
                        if not printed_prefix:
                            print("\nGemini: ", end="", flush=True)
                            printed_prefix = True
                        print(text, end="", flush=True)
        except asyncio.CancelledError:
            logger.info("Response listener cancelled")
            raise
        except (ConnectionClosedOK, ConnectionClosedError) as e:
            # Normal websocket closure - not an error
            logger.info(f"Gemini connection closed: {e}")
        except Exception as e:
            logger.error(f"Error in receive_responses: {e}")
            raise
    
    async def send_text_message(self, message: str):
        """Send text message to Gemini API."""
        try:
            await self.session.send(input=message, end_of_turn=True)
        except Exception as e:
            logger.error(f"Error sending text message: {e}")
            raise
    
    async def cleanup_session(self):
        """Clean up Gemini session."""
        if hasattr(self, 'session_context') and self.session_context:
            try:
                # Call __aexit__ on the context manager, not the session
                await self.session_context.__aexit__(None, None, None)
                logger.info("✅ Gemini session closed successfully.")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
        
        # Clear references
        self.session = None
        self.session_context = None
    
    def get_metadata(self):
        """Return Gemini-specific metadata."""
        base_metadata = super().get_metadata()
        return {
            **base_metadata,
            "provider": "Gemini",
            "model": self.MODEL
        }


def main():
    """Main entry point with CLI."""
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser(
        description="Process RTSP stream with Gemini Live API."
    )
    parser.add_argument("--rtsp-url", type=str, required=True)
    parser.add_argument(
        "--focus",
        type=str,
        default="audio_video",
        choices=["audio_video", "audio_only", "video_only"]
    )
    args = parser.parse_args()
    
    processor = GeminiStreamProcessor(
        rtsp_url=args.rtsp_url,
        focus=args.focus
    )
    
    try:
        asyncio.run(processor.run())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting.")


if __name__ == "__main__":
    main()