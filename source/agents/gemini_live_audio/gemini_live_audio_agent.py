# -*- coding: utf-8 -*-
"""
Gemini RTSP Stream Processor - Implements Gemini-specific API communication
"""

import os
from textwrap import dedent
from google import genai
from loguru import logger
from dotenv import load_dotenv
from source.agents.base_processor import BaseStreamProcessor
from .prompt import PROMPTS

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
    
    async def initialize_session(self):
        """Initialize Gemini Live API session."""
        self.session = await self.client.aio.live.connect(
            model=self.MODEL,
            config=self.config
        ).__aenter__()
        logger.info("Connected to Gemini Live API.")
    
    async def send_realtime_data(self):
        """Send media from queue to Gemini API."""
        logger.info("Realtime media sending started.")
        while True:
            payload = await self.out_queue.get()
            await self.session.send(input=payload)
            self.out_queue.task_done()
    
    async def receive_responses(self):
        """Receive text responses from Gemini API and print to console."""
        logger.info("Response listener started.")
        while True:
            turn = self.session.receive()
            printed_prefix = False
            async for response in turn:
                if text := response.text:
                    if not printed_prefix:
                        print("\nGemini: ", end="", flush=True)
                        printed_prefix = True
                    print(text, end="", flush=True)
    
    async def send_text_message(self, message: str):
        """Send text message to Gemini API."""
        await self.session.send(input=message, end_of_turn=True)
    
    async def cleanup_session(self):
        """Clean up Gemini session."""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
                logger.info("Gemini session closed.")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
    
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