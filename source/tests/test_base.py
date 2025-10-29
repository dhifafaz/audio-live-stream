"""
Unit tests for BaseStreamProcessor.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from source.agents.base_processor import BaseStreamProcessor


class TestBaseStreamProcessor:
    """Test suite for BaseStreamProcessor abstract class."""
    
    def test_base_processor_is_abstract(self):
        """Test that BaseStreamProcessor cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            BaseStreamProcessor(rtsp_url="rtsp://test", focus="audio")
        
        assert "Can't instantiate abstract class" in str(exc_info.value)
    
    def test_base_processor_subclass_creation(self):
        """Test creating a valid subclass of BaseStreamProcessor."""
        
        class TestProcessor(BaseStreamProcessor):
            async def initialize_session(self):
                pass
            
            async def send_realtime_data(self, audio_chunk=None, video_frame=None):
                pass
            
            async def receive_responses(self):
                pass
            
            async def send_text_message(self, text: str):
                pass
            
            async def cleanup_session(self):
                pass
        
        processor = TestProcessor(rtsp_url="rtsp://test:554/stream", focus="audio_video")
        
        assert processor.rtsp_url == "rtsp://test:554/stream"
        assert processor.focus == "audio_video"
        assert processor.running is False
        assert processor.queue.maxsize == 100
    
    @pytest.mark.asyncio
    async def test_queue_operations(self):
        """Test queue put and get operations."""
        
        class TestProcessor(BaseStreamProcessor):
            async def initialize_session(self):
                self.session = "mock_session"
            
            async def send_realtime_data(self, audio_chunk=None, video_frame=None):
                pass
            
            async def receive_responses(self):
                while self.running:
                    await asyncio.sleep(0.1)
            
            async def send_text_message(self, text: str):
                pass
            
            async def cleanup_session(self):
                pass
        
        processor = TestProcessor(rtsp_url="rtsp://test", focus="audio")
        
        # Test queue operations
        await processor.queue.put({"type": "audio", "data": "test_audio"})
        item = await processor.queue.get()
        
        assert item["type"] == "audio"
        assert item["data"] == "test_audio"
    
    @pytest.mark.asyncio
    async def test_stop_method(self):
        """Test processor stop method."""
        
        class TestProcessor(BaseStreamProcessor):
            async def initialize_session(self):
                pass
            
            async def send_realtime_data(self, audio_chunk=None, video_frame=None):
                pass
            
            async def receive_responses(self):
                pass
            
            async def send_text_message(self, text: str):
                pass
            
            async def cleanup_session(self):
                self.cleanup_called = True
        
        processor = TestProcessor(rtsp_url="rtsp://test", focus="audio")
        processor.running = True
        
        await processor.stop()
        
        assert processor.running is False
        assert processor.cleanup_called is True
    
    @pytest.mark.asyncio
    async def test_focus_modes(self):
        """Test different focus modes (audio, video, audio_video)."""
        
        class TestProcessor(BaseStreamProcessor):
            async def initialize_session(self):
                pass
            
            async def send_realtime_data(self, audio_chunk=None, video_frame=None):
                pass
            
            async def receive_responses(self):
                pass
            
            async def send_text_message(self, text: str):
                pass
            
            async def cleanup_session(self):
                pass
        
        # Test audio-only
        audio_processor = TestProcessor(rtsp_url="rtsp://test", focus="audio_only")
        assert audio_processor.focus == "audio_only"
        
        # Test video-only
        video_processor = TestProcessor(rtsp_url="rtsp://test", focus="video_only")
        assert video_processor.focus == "video_only"
        
        # Test audio-video
        av_processor = TestProcessor(rtsp_url="rtsp://test", focus="audio_video")
        assert av_processor.focus == "audio_video"