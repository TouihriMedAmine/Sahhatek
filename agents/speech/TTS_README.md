# Arabic Text-to-Speech (TTS) Service

This module provides Arabic Text-to-Speech functionality using Microsoft Edge TTS with multiple speaker voices.

## Features

- ✅ Arabic TTS with high-quality voices
- ✅ Multiple speaker options (male, female, different accents)
- ✅ Support for other languages (English, French, etc.)
- ✅ Easy-to-use API
- ✅ Base64 audio output for web integration
- ✅ Works with Python 3.12+
- ✅ Free and no API key required

## Installation

### 1. Install Edge TTS

```bash
pip install edge-tts
```

### 2. No Model Download Required

Edge TTS uses Microsoft's cloud-based TTS service, so no model download is needed. It supports:
- Arabic (ar-SA, ar-EG, ar-AE, etc.)
- English (en-US, en-GB, etc.)
- French (fr-FR)
- Spanish (es-ES)
- German (de-DE)
- Italian (it-IT)
- Portuguese (pt-BR)
- And 100+ more languages and voices

## Usage

### Python API

```python
from agents.speech.tts_service import TTSService

# Get TTS service instance
tts = TTSService.get_instance()

# Synthesize speech
audio_data = tts.synthesize("مرحبا بك في نظام الصحة", speaker="female_arabic_1")

# Save to file
with open("output.wav", "wb") as f:
    f.write(audio_data)

# Get available speakers
speakers = tts.get_speakers()
print(f"Available speakers: {speakers}")

# Set default speaker
tts.set_speaker("male_arabic_1")
```

### Django API Endpoint

#### POST `/chat/api/text-to-speech/`

Convert text to speech.

**Request:**
```json
{
  "text": "مرحبا بك في نظام الصحة",
  "speaker": "female_arabic_1",  // Optional
  "language": "ar"  // Optional, default: "ar"
}
```

**Response:**
```json
{
  "success": true,
  "audio": "base64_encoded_audio_data",
  "format": "wav",
  "speakers": ["female_arabic_1", "female_arabic_2", "male_arabic_1", ...],
  "current_speaker": "female_arabic_1",
  "message": "Speech synthesized successfully"
}
```

#### GET `/chat/api/text-to-speech/`

Get available speakers.

**Response:**
```json
{
  "success": true,
  "speakers": ["female_arabic_1", "female_arabic_2", "male_arabic_1", ...],
  "available": true
}
```

### Frontend Integration

```javascript
// Synthesize speech
async function synthesizeSpeech(text, speaker = null) {
  const response = await fetch('/chat/api/text-to-speech/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCSRFToken()
    },
    body: JSON.stringify({
      text: text,
      speaker: speaker,
      language: 'ar'
    })
  });
  
  const data = await response.json();
  
  if (data.success && data.audio) {
    // Decode base64 audio
    const audioData = atob(data.audio);
    const audioBytes = new Uint8Array(audioData.length);
    for (let i = 0; i < audioData.length; i++) {
      audioBytes[i] = audioData.charCodeAt(i);
    }
    
    // Create audio blob and play
    const audioBlob = new Blob([audioBytes], { type: 'audio/wav' });
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.play();
  }
}

// Get available speakers
async function getSpeakers() {
  const response = await fetch('/chat/api/text-to-speech/');
  const data = await response.json();
  return data.speakers || [];
}
```

## Available Speakers

The XTTS-v2 model comes with multiple built-in speakers:

- `female_arabic_1` - Female Arabic voice 1
- `female_arabic_2` - Female Arabic voice 2
- `male_arabic_1` - Male Arabic voice 1
- `male_arabic_2` - Male Arabic voice 2
- `neutral_arabic` - Neutral Arabic voice

Note: The actual available speakers may vary based on the model version. Use the GET endpoint to see all available speakers.

## Supported Languages

- Arabic (ar) - Primary
- English (en)
- French (fr)
- Spanish (es)
- German (de)
- Italian (it)
- Portuguese (pt)
- Polish (pl)
- Turkish (tr)
- Russian (ru)
- Dutch (nl)
- Czech (cs)
- Chinese (zh-cn)
- Japanese (ja)
- Hungarian (hu)
- Korean (ko)

## Performance Notes

- First synthesis may take longer as the model loads
- Subsequent requests are faster
- GPU acceleration is supported (set `gpu=True` in `tts_service.py`)
- Audio output is in WAV format (16kHz, mono)

## Troubleshooting

### Model not loading
- Ensure TTS library is installed: `pip install TTS`
- Check internet connection (model downloads on first use)
- Verify sufficient disk space (~2GB for model)

### No audio output
- Check server logs for errors
- Verify text is not empty
- Ensure speaker name is valid (use GET endpoint to check)

### Slow synthesis
- Consider using GPU if available
- Reduce text length for faster processing
- Model loads once, subsequent requests are faster

