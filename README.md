# Tactical Audio Analysis System

A real-time audio analysis system designed for tactical operations, capable of detecting verbal escalation and threatening language in Indonesian across multiple dialects. The system processes RTSP audio streams and provides instant alert classifications based on acoustic patterns, emotional intensity, and linguistic indicators.

## Overview

This system monitors live audio streams to detect signs of escalation in public or interpersonal situations (demonstrations, police interactions, heated discussions) and classifies them into three alert levels: **GREEN** (calm), **YELLOW** (potential escalation), and **RED** (critical danger).

## Features

- 🎤 **Real-time Audio/Video Processing**: Streams audio from RTSP sources using FFmpeg, base64
- 🤖 **AI-Powered Analysis**: Uses Qwen Omni API for multi-modal audio understanding
- 🚨 **Three-Level Alert System**: GREEN → YELLOW → RED escalation detection
- 🌐 **Multilanguage and or Multi-Dialect Support**: Analyzes Indonesian with regional variations 
- 📊 **Acoustic Analysis**: Monitors volume, pitch, speed, and breathing patterns
- 🔄 **WebSocket Integration**: Real-time alert delivery via WebSocket
- 🔁 **Auto-Reconnection**: Robust reconnection logic with exponential backoff
- 📝 **Audio Transcription**: Real-time transcription with gummy-realtime-v1 model

## System Architecture
 Gemini 
```
┌─────────────────────────────────────────────────────────────┐
│                   RTSP STREAM                               │
│              rtsp://camera-ip/stream                        │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │        FFmpeg Process           │
        │  • Audio: PCM bytes stream      │
        │  • Video: JPEG frames stream    │
        └─────────────────────────────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
                ▼                   ▼
    ┌───────────────────┐   ┌───────────────────┐
    │  capture_audio()  │   │  capture_video()  │
    │  (base_processor) │   │  (base_processor) │
    └───────────────────┘   └───────────────────┘
                │                   │
                ▼                   ▼
        audio_chunk (bytes)   video_frame (base64)
                │                   │
                ▼                   ▼
    ┌───────────────────────────────────────────┐
    │   send_realtime_data()                    │
    │   (gemini_processor)                      │
    │   • Validates data type                   │
    │   • Logs data received                    │
    └───────────────────────────────────────────┘
                          │
                          ▼
            ┌──────────────────────┐
            │      out_queue       │
            │   (asyncio.Queue)    │
            └──────────────────────┘
                          │
                          ▼
    ┌───────────────────────────────────────────┐
    │   send_realtime_from_queue()              │
    │   • Dequeue payload                       │
    │   • Send to Gemini API                    │
    └───────────────────────────────────────────┘
                          │
                          ▼
            ┌──────────────────────┐
            │    Gemini API        │
            │  Processing...       │
            └──────────────────────┘
                          │
                          ▼
    ┌───────────────────────────────────────────┐
    │   receive_responses()                     │
    │   • Accumulate response                   │
    │   • Parse JSON or text                    │
    │   • Send to WebSocket                     │
    └───────────────────────────────────────────┘
```


Qwen
```

## Installation

### Prerequisites

1. **Python 3.10+**
2. **FFmpeg** - Must be installed and accessible in PATH
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install ffmpeg
   
   # macOS
   brew install ffmpeg
   
   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

3. **DashScope API Key**
   - Sign up at https://dashscope.aliyuncs.com/
   - Get your API key

### Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd tactical-audio-analysis

# Install Python packages
pip install dashscope asyncio

# Verify FFmpeg installation
ffmpeg -version
```

### Configuration

Set your DashScope API key:

```bash
# Option 1: Environment variable (recommended for production)
export DASHSCOPE_API_KEY="your-api-key-here"

# Option 2: Direct in code (for development only)
# Edit the processor file and replace:
dashscope.api_key = 'your-api-key-here'
```

## Usage

### Standalone Mode

#### Audio-Only Processing
```bash
python qwen_rtsp_processor.py --rtsp-url "rtsp://username:password@host:port/path"
```

Example:
```bash
python qwen_rtsp_processor.py --rtsp-url "rtsp://streamer:Rahas!@2025@10.254.1.252:8554/bodycam"
```

#### Audio + Video Processing
```bash
python qwen_rtsp_processor_av.py \
  --rtsp-url "rtsp://username:password@host:port/path" \
  --focus av
```

Available focus modes:
- `audio` - Audio-only analysis
- `av` - Audio + Video analysis

### Integration with WebSocket

```python
from rtsp_processor import RTSPStreamProcessor

# Initialize with WebSocket connection
processor = RTSPStreamProcessor(
    rtsp_url="rtsp://your-stream-url",
    websocket=your_websocket_connection
)

# Run the processor
await processor.run()

# Stop gracefully
await processor.stop()
```

### WebSocket Alert Format

The system sends alerts via WebSocket in JSON format:

```json
{
  "alert": "yellow",
  "keywords": ["awas ya", "jangan main-main"],
  "visual_indicators": []
}
```


## Logging

The system provides comprehensive logging:

```
2025-01-27 10:30:45 - INFO - Initializing Qwen Omni connection...
2025-01-27 10:30:46 - INFO - ✓ Session started: session-abc123
2025-01-27 10:30:47 - INFO - Starting audio stream capture with FFmpeg...
2025-01-27 10:30:48 - INFO - FFmpeg process started, waiting for audio data...
2025-01-27 10:30:50 - INFO - 🔊 Speech detected in audio stream
2025-01-27 10:30:52 - INFO - 🎤 Transcription: awas ya jangan main-main
2025-01-27 10:30:53 - INFO - 📝 Text delta: {"alert": "yellow"
2025-01-27 10:30:54 - INFO - ✓ Full text response: {"alert": "yellow", "keywords": ["awas ya"]}
2025-01-27 10:30:54 - INFO - 🚨 Alert sent: {'alert': 'yellow', 'keywords': ['awas ya']}
```

## Performance

### Resource Usage
- **Memory**: ~200-500 MB
- **CPU**: ~10-30% (single core)
- **Network**: ~128 kbps audio upload
- **Latency**: 1-3 seconds from audio to alert

### Optimization Tips
1. **Buffer Duration**: Adjust `audio_buffer_duration` based on response time needs
2. **Chunk Size**: Keep at 3200 bytes for optimal Qwen API processing
3. **Network**: Use TCP transport for RTSP reliability
4. **Reconnection**: Exponential backoff prevents API rate limiting


## Deployment

### Docker Deployment

```dockerfile
FROM python:3.10-slim

# Install FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DASHSCOPE_API_KEY=""

CMD ["python", "qwen_rtsp_processor.py", "--rtsp-url", "${RTSP_URL}"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tactical-audio-analysis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: tactical-audio
  template:
    metadata:
      labels:
        app: tactical-audio
    spec:
      containers:
      - name: processor
        image: tactical-audio:latest
        env:
        - name: DASHSCOPE_API_KEY
          valueFrom:
            secretKeyRef:
              name: dashscope-secret
              key: api-key
        - name: RTSP_URL
          value: "rtsp://stream-url"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

### Systemd Service

```ini
[Unit]
Description=Tactical Audio Analysis Service
After=network.target

[Service]
Type=simple
User=tactical
WorkingDirectory=/opt/tactical-audio
Environment="DASHSCOPE_API_KEY=your-key"
ExecStart=/usr/bin/python3 qwen_rtsp_processor.py --rtsp-url "rtsp://stream"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Monitoring & Observability

### Health Check
Monitor the following indicators:
- FFmpeg process status
- Qwen API connection state
- Audio chunk processing rate
- WebSocket connection status
- Alert delivery latency

### Metrics to Track
- **Audio Chunks Sent**: Counter
- **Alerts Generated**: Counter by level (green/yellow/red)
- **API Response Time**: Histogram
- **Reconnection Attempts**: Counter
- **FFmpeg Errors**: Counter

### Example Prometheus Metrics
```python
from prometheus_client import Counter, Histogram

audio_chunks_sent = Counter('audio_chunks_sent_total', 'Total audio chunks sent')
alerts_generated = Counter('alerts_generated_total', 'Alerts by level', ['level'])
api_response_time = Histogram('api_response_seconds', 'API response time')
```

## Troubleshooting

### High Memory Usage
- Reduce `audio_buffer_duration`
- Check for memory leaks in event loop
- Monitor FFmpeg process memory

### Delayed Alerts
- Check network latency to Qwen API
- Reduce `RESPONSE_INTERVAL`
- Verify RTSP stream quality

### Missing Transcriptions
- Verify `enable_input_audio_transcription=True`
- Check audio quality (volume, clarity)
- Ensure proper language model (`gummy-realtime-v1`)

### Frequent Reconnections
- Check network stability
- Verify API key validity
- Review API rate limits
- Increase `RECONNECT_BACKOFF`

## Contributing

### Development Setup
```bash
# Clone repository
git clone <repo-url>
cd tactical-audio-analysis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-asyncio black flake8
```

### Code Style
```bash
# Format code
black *.py

# Lint code
flake8 *.py
```

### Testing
```bash
# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## License


## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Contact: [your-email@example.com]
- Documentation: [link-to-docs]

## Changelog

### Version 1.0.0 (Current)
- ✅ Real-time audio stream processing
- ✅ Three-level alert classification
- ✅ Multi-dialect Indonesian and Multilingual support
- ✅ WebSocket integration
- ✅ Auto-reconnection with backoff
- ✅ Audio transcription
- ✅ Comprehensive logging

### Planned Features
- [ ] Video analysis integration
- [ ] Multi-language support (English, Tagalog)
- [ ] Alert history tracking
- [ ] Dashboard for monitoring
- [ ] Batch processing mode
- [ ] Custom alert rules engine
- [ ] Audio quality metrics
- [ ] Performance benchmarking

## Acknowledgments

- **Qwen Omni API** by Alibaba Cloud (DashScope)
- **FFmpeg** for audio processing
- Indonesian linguistics research for dialect patterns
- Open source community

---

**⚠️ Disclaimer**: This system is designed for tactical operations and security applications. Use responsibly and in accordance with local laws and regulations regarding audio monitoring and privacy.