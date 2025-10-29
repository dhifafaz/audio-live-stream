from pydantic.v1 import BaseSettings
from dotenv import load_dotenv
from typing import Optional 
import os, sys
path_this = os.path.dirname(os.path.abspath(__file__))
path_project = os.path.dirname(os.path.join(path_this, '..'))
path_root = os.path.dirname(os.path.join(path_this, '../..'))
sys.path.append(path_root)
sys.path.append(path_project)
sys.path.append(path_this)

class AppConfig(BaseSettings):
    
    DASHCOPE_API_KEY: Optional[str]
    SEND_SAMPLE_RATE: int = 16000
    AUDIO_CHUNK_SIZE: int = 1280  # 100ms chunks
    VIDEO_CHUNK_INTERVAL: float = 0.5  # seconds between video frame sends
    RESPONSE_INTERVAL: float = 2.0  # Request response every 2 seconds for real-time analysis
    RECONNECT_BACKOFF: float = 2.0  # seconds initial backoff for reconnect attempts
    MAX_RECONNECT_BACKOFF: float = 60.0
    MODEL: str = "qwen3-omni-flash-realtime"
    
    GOOGLE_API_KEY: Optional[str]
    GOOGLE_MODEL: str = "models/gemini-2.0-flash-live-001"
    RTSP_URL: Optional[str]
    WEBSOCKET_URL_GEMINI: Optional[str]
    WEBSOCKET_URL_QWEN: Optional[str]
    

    class Config:
        env_file = os.path.join(path_root, ".env")

    load_dotenv(".env", override=True)

settings = AppConfig()