from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Enums
class AlertLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class FocusMode(str, Enum):
    AUDIO_ONLY = "Audio"
    AUDIO_VIDEO = "Audio + Video"

class MonitoringStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"

# Detection Output Model
class DetectionOutputModel(BaseModel):
    keywords: str = Field(..., description="Kata kunci yang terdeteksi")
    alert: AlertLevel = Field(..., description="Level alert")
    visual_indicators: str = Field(..., description="Indikator visual yang terdeteksi")

# RTSP Configuration Model
class RTSPConfigModel(BaseModel):
    rtsp_url: str = Field(..., description="URL RTSP stream")
    focus_mode: FocusMode = Field(FocusMode.AUDIO_VIDEO, description="Mode fokus monitoring")
    
    @field_validator('rtsp_url')
    @classmethod
    def validate_rtsp_url(cls, v):
        if not v.startswith('rtsp://'):
            raise ValueError("URL harus dimulai dengan 'rtsp://'")
        return v

# Input Data Model (seperti InputDataModel di attachment 1)
class MonitoringInputModel(BaseModel):
    alert: AlertLevel = Field(AlertLevel.LOW, description="Minimum alert level untuk notifikasi")
    keywords: Optional[List[str]] = Field(None, description="Filter kata kunci spesifik")
    rtsp_config: RTSPConfigModel = Field(..., description="Konfigurasi RTSP stream")

# # Processing Response Model 
# class MonitoringResponseModel(BaseModel):
#     status: MonitoringStatus
#     message: str
#     session_id: Optional[str] = None
#     detection_count: Optional[int] = None
#     processing_time: Optional[float] = None
#     latest_detection: Optional[DetectionOutputModel] = None

# Error Response Model
class ErrorResponseModel(BaseModel):
    status: MonitoringStatus = MonitoringStatus.ERROR
    message: str
    error_code: Optional[str] = None

# Health Check Model
class HealthCheckModel(BaseModel):
    status: str
    timestamp: datetime
    service: str