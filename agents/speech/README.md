# Real-time Arabic Transcription Service

This module provides real-time Arabic/Tunisian dialect transcription using Vosk models.

## Features

- ✅ Real-time streaming transcription
- ✅ Arabic text reshaping for proper display
- ✅ Batch audio transcription
- ✅ Gradio web interface
- ✅ Integration with Django agents

## Installation

Make sure you have the required dependencies:

```bash
pip install vosk sounddevice arabic-reshaper gradio
```

## Usage

### Standalone Script

Run the standalone transcription interface:

```bash
python transcription_arabe_realtime.py
```

This will launch a Gradio web interface where you can:
1. Click "Submit" to start recording
2. Speak in Tunisian Arabic dialect
3. See real-time transcription with properly connected Arabic letters
4. Click "Stop" to end recording

### As a Python Module

#### Real-time Streaming

```python
from agents.speech.transcription import TranscriptionService

# Get transcription generator
transcription = TranscriptionService.get_instance()

# Start real-time transcription
for text in transcription.transcribe_generator():
    print(text)
    # Process text as it comes in...
    
# Stop when done
transcription.stop()
```

#### Batch Transcription

```python
from agents.speech.transcription import TranscriptionService

# Transcribe audio data
audio_bytes = ...  # Your audio data (16kHz, mono, int16)
transcription = TranscriptionService.transcribe_audio(audio_bytes)
print(transcription)
```

#### Direct Usage

```python
from agents.speech.transcription import RealTimeTranscription

# Initialize with model path
transcription = RealTimeTranscription(model_path="path/to/vosk-model")

# Use methods
text = transcription.transcribe_audio_data(audio_bytes)
# or
for text in transcription.transcribe_generator():
    print(text)
```

## Model Path

The service automatically searches for the Vosk model in these locations:
1. `Modele_huhugging/vosk-model/vosk-model`
2. `maaaheeeerrr/Modele_huhugging/vosk-model/vosk-model`
3. Relative paths from the module location

You can also specify a custom path:

```python
transcription = RealTimeTranscription(model_path="/path/to/your/model")
```

## Integration with Django

The `SpeechHandler` in `agents/understanding_agent/agent.py` automatically uses this service for audio transcription.

## Configuration

- **Sample Rate**: 16000 Hz (required by Vosk)
- **Block Size**: 4000 samples
- **Audio Format**: 16-bit PCM, mono channel

## Notes

- Arabic text is automatically reshaped to connect letters properly
- RTL (right-to-left) display is handled via CSS in the Gradio interface
- The service supports mixed Arabic/French/English text
- Real-time transcription shows both partial (during speech) and final results

