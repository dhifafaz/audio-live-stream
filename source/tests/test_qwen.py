"""
Unit tests for QwenProcessor.
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch, MagicMock, call
from source.agents.qwen_live_audio.qwen_live_audio_agent import (
    QwenProcessor, 
    QwenCallback
)


class TestQwenCallback:
    """Test suite for QwenCallback."""
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock websocket."""
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        return ws
    
    @pytest.fixture
    def mock_loop(self):
        """Create a mock event loop."""
        loop = Mock()
        loop.time = Mock(return_value=1000.0)
        return loop
    
    @pytest.fixture
    def callback(self, mock_websocket, mock_loop):
        """Create a QwenCallback instance."""
        return QwenCallback(websocket=mock_websocket, loop=mock_loop)
    
    def test_callback_initialization(self, callback, mock_websocket, mock_loop):
        """Test callback initialization."""
        assert callback.websocket == mock_websocket
        assert callback.loop == mock_loop
        assert callback.session_id is None
        assert callback.accumulated_text == ""
    
    def test_on_open(self, callback):
        """Test on_open callback."""
        # Should not raise any exception
        callback.on_open()
    
    def test_on_close_normal(self, callback):
        """Test on_close with normal close status."""
        callback.on_close(1000, "Normal closure")
        # Should not trigger reconnection
    
    def test_on_close_abnormal(self, callback, mock_loop):
        """Test on_close with abnormal status triggers reconnection."""
        reconnect_callback = AsyncMock()
        callback.reconnect_callback = reconnect_callback
        
        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            callback.on_close(1006, "Abnormal closure")
            mock_run.assert_called_once()
    
    def test_on_event_session_created(self, callback):
        """Test session.created event."""
        response = {
            'type': 'session.created',
            'session': {'id': 'test-session-123'}
        }
        
        callback.on_event(response)
        
        assert callback.session_id == 'test-session-123'
    
    def test_on_event_transcription(self, callback):
        """Test transcription completed event."""
        response = {
            'type': 'conversation.item.input_audio_transcription.completed',
            'transcript': 'Hello world'
        }
        
        callback.on_event(response)
        # Should log but not store anything
    
    def test_on_event_text_delta(self, callback):
        """Test text delta accumulation."""
        callback.on_event({'type': 'response.text.delta', 'delta': 'Hello '})
        callback.on_event({'type': 'response.text.delta', 'delta': 'world'})
        
        assert callback.accumulated_text == 'Hello world'
    
    def test_on_event_text_done(self, callback):
        """Test text done with alert parsing."""
        callback.accumulated_text = "Some text"
        
        with patch.object(callback, '_try_send_alert') as mock_send:
            response = {'type': 'response.text.done', 'text': '{"alert": "test"}'}
            callback.on_event(response)
            
            mock_send.assert_called_once_with('{"alert": "test"}')
            assert callback.accumulated_text == ""
    
    def test_on_event_response_done(self, callback):
        """Test response done event."""
        callback.accumulated_text = '{"alert": "fire"}'
        
        with patch.object(callback, '_try_send_alert') as mock_send:
            callback.on_event({'type': 'response.done'})
            
            mock_send.assert_called_once()
            assert callback.accumulated_text == ""
    
    def test_try_send_alert_valid_json(self, callback, mock_websocket, mock_loop):
        """Test sending valid JSON alert."""
        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            callback._try_send_alert('{"alert": "fire", "description": "test"}')
            
            mock_run.assert_called_once()
    
    def test_try_send_alert_invalid_json(self, callback):
        """Test handling invalid JSON."""
        # Should not raise exception
        callback._try_send_alert("Not a JSON string")
    
    def test_try_send_alert_json_extraction(self, callback, mock_loop):
        """Test extracting JSON from text."""
        text = 'Some text before {"alert": "test"} some text after'
        
        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            callback._try_send_alert(text)
            
            mock_run.assert_called_once()


class TestQwenProcessor:
    """Test suite for QwenProcessor."""
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock websocket."""
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        return ws
    
    @pytest.fixture
    def processor(self, mock_websocket):
        """Create a QwenProcessor instance."""
        return QwenProcessor(
            rtsp_url="rtsp://test:554/stream",
            websocket=mock_websocket,
            focus="audio_video"
        )
    
    def test_processor_initialization(self, processor, mock_websocket):
        """Test processor initialization."""
        assert processor.rtsp_url == "rtsp://test:554/stream"
        assert processor.websocket == mock_websocket
        assert processor.focus == "audio_video"
        assert processor.conversation is None
        assert processor.reconnect_attempts == 0
    
    @pytest.mark.asyncio
    async def test_initialize_session_success(self, processor):
        """Test successful session initialization."""
        mock_conversation = Mock()
        mock_conversation.connect = Mock()
        mock_conversation.update_session = Mock()
        
        with patch('source.agents.qwen_live_audio.qwen_live_audio_agent.OmniRealtimeConversation') as mock_conv_class, \
             patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread, \
             patch('asyncio.get_event_loop') as mock_loop:
            
            mock_conv_class.return_value = mock_conversation
            mock_to_thread.return_value = None
            
            await processor.initialize_session()
            
            assert processor.conversation is not None
            assert processor.reconnect_attempts == 0
    
    @pytest.mark.asyncio
    async def test_initialize_session_failure_triggers_reconnect(self, processor):
        """Test initialization failure triggers reconnection."""
        processor.running = True
        
        with patch('source.agents.qwen_live_audio.qwen_live_audio_agent.OmniRealtimeConversation') as mock_conv, \
             patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread, \
             patch.object(processor, '_handle_reconnect', new_callable=AsyncMock) as mock_reconnect:
            
            mock_to_thread.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception):
                await processor.initialize_session()
    
    @pytest.mark.asyncio
    async def test_send_realtime_data_audio(self, processor):
        """Test sending audio data."""
        mock_conversation = Mock()
        mock_conversation.append_audio = Mock()
        processor.conversation = mock_conversation
        
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            await processor.send_realtime_data(audio_chunk="base64_audio_data")
            
            mock_to_thread.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_realtime_data_video(self, processor):
        """Test sending video data."""
        mock_conversation = Mock()
        mock_conversation.append_video = Mock()
        processor.conversation = mock_conversation
        
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            await processor.send_realtime_data(video_frame="base64_video_frame")
            
            mock_to_thread.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_realtime_data_both(self, processor):
        """Test sending both audio and video data."""
        mock_conversation = Mock()
        mock_conversation.append_audio = Mock()
        mock_conversation.append_video = Mock()
        processor.conversation = mock_conversation
        
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            await processor.send_realtime_data(
                audio_chunk="audio_data",
                video_frame="video_data"
            )
            
            assert mock_to_thread.call_count == 2
    
    @pytest.mark.asyncio
    async def test_send_realtime_data_no_conversation(self, processor):
        """Test sending data without initialized conversation."""
        processor.conversation = None
        
        # Should not raise exception, just log warning
        await processor.send_realtime_data(audio_chunk="test")
    
    @pytest.mark.asyncio
    async def test_send_text_message(self, processor, mock_websocket):
        """Test sending text message."""
        mock_conversation = Mock()
        mock_conversation.append_text = Mock()
        mock_conversation.create_response = Mock()
        processor.conversation = mock_conversation
        
        with patch('asyncio.to_thread', new_callable=AsyncMock):
            await processor.send_text_message("Hello Qwen")
            
            mock_websocket.send_json.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_reconnect_success(self, processor):
        """Test successful reconnection."""
        processor.running = True
        processor.reconnect_attempts = 0
        
        with patch.object(processor, 'initialize_session', new_callable=AsyncMock) as mock_init:
            await processor._handle_reconnect()
            
            mock_init.assert_called_once()
            assert processor.is_reconnecting is False
    
    @pytest.mark.asyncio
    async def test_handle_reconnect_max_attempts(self, processor):
        """Test reconnection stops after max attempts."""
        processor.running = True
        processor.reconnect_attempts = 5  # MAX_RECONNECT_ATTEMPTS
        
        await processor._handle_reconnect()
        
        assert processor.running is False
    
    @pytest.mark.asyncio
    async def test_handle_reconnect_exponential_backoff(self, processor):
        """Test exponential backoff in reconnection."""
        processor.running = True
        processor.reconnect_attempts = 1
        processor.reconnect_delay = 2.0
        
        with patch.object(processor, 'initialize_session', new_callable=AsyncMock) as mock_init, \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            mock_init.side_effect = Exception("Still failing")
            
            await processor._handle_reconnect()
            
            # Backoff should double
            assert processor.reconnect_delay == 4.0
    
    @pytest.mark.asyncio
    async def test_cleanup_session(self, processor):
        """Test session cleanup."""
        mock_conversation = Mock()
        mock_conversation.close = Mock()
        processor.conversation = mock_conversation
        
        with patch('asyncio.to_thread', new_callable=AsyncMock):
            await processor.cleanup_session()
            
            assert processor.running is False
    
    @pytest.mark.asyncio
    async def test_receive_responses(self, processor):
        """Test receive_responses task."""
        processor.running = True
        
        # Create task and cancel after short time
        task = asyncio.create_task(processor.receive_responses())
        await asyncio.sleep(0.1)
        processor.running = False
        await asyncio.sleep(0.1)
        
        assert task.done()


class TestQwenProcessorIntegration:
    """Integration tests for QwenProcessor."""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test full processor lifecycle."""
        mock_ws = AsyncMock()
        processor = QwenProcessor(
            rtsp_url="rtsp://test:554/stream",
            websocket=mock_ws,
            focus="audio"
        )
        
        # Mock all external dependencies
        with patch('source.agents.qwen_live_audio.qwen_live_audio_agent.OmniRealtimeConversation'), \
             patch('asyncio.to_thread', new_callable=AsyncMock), \
             patch('asyncio.get_event_loop') as mock_loop:
            
            mock_loop.return_value.time.return_value = 1000.0
            
            # Initialize
            await processor.initialize_session()
            assert processor.conversation is not None
            
            # Send data
            await processor.send_realtime_data(audio_chunk="test_audio")
            
            # Cleanup
            await processor.cleanup_session()
            assert processor.running is False