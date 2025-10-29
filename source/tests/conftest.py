"""
Pytest configuration and shared fixtures.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_rtsp_url():
    """Provide a mock RTSP URL."""
    return "rtsp://test:password@10.0.0.1:554/stream"


@pytest.fixture
def mock_websocket():
    """Provide a mock WebSocket connection."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-api-key-123")
    monkeypatch.setenv("SEND_SAMPLE_RATE", "16000")
    monkeypatch.setenv("AUDIO_CHUNK_SIZE", "1280")
    monkeypatch.setenv("VIDEO_CHUNK_INTERVAL", "1.5")
    monkeypatch.setenv("RESPONSE_INTERVAL", "2.0")
    monkeypatch.setenv("RECONNECT_BACKOFF", "2.0")
    monkeypatch.setenv("MAX_RECONNECT_BACKOFF", "60.0")
    monkeypatch.setenv("MAX_RECONNECT_ATTEMPTS", "5")