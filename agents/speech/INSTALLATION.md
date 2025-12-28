# Audio Transcription Installation Guide

## Required Dependencies

### Python Packages
```bash
pip install vosk sounddevice arabic-reshaper pydub
```

### FFmpeg (Required for WebM/Opus audio conversion)

**Windows:**
1. Download from https://ffmpeg.org/download.html
2. Extract to a folder (e.g., `C:\ffmpeg`)
3. Add to PATH or set environment variable:
   ```powershell
   $env:Path += ";C:\ffmpeg\bin"
   ```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## Verification

After installation, test the audio conversion:

```python
from agents.speech.transcription import TranscriptionService
import base64

# Test with sample audio
transcription = TranscriptionService.get_instance()
# The service will automatically convert WebM/Opus to PCM
```

## Troubleshooting

### "Could not transcribe audio"
- Ensure ffmpeg is installed and in PATH
- Check that pydub is installed: `pip install pydub`
- Verify Vosk model is in the correct location

### Audio conversion errors
- Check ffmpeg installation: `ffmpeg -version`
- Ensure audio format is supported (WebM, Opus, MP4, WAV)

