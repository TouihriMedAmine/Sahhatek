# 🩹 Wound Analyzer Agent - Complete Setup Guide

## Overview
The Wound Analyzer is a specialized AI agent that analyzes images of wounds, rashes, and skin conditions using computer vision technology. It's integrated into the Sahatek health assistant platform.

## Architecture

### 1. **Frontend** ([static/js/main.js](../../static/js/main.js))
- **Agent ID**: `computer-vision`
- **Display Title**: `Wound Analyzer`
- **Welcome Message**: "Hello! I'm your wound analysis assistant. You can upload images of wounds, rashes, or skin conditions for analysis."
- **Chat Creation**: `window.chatManager.createAgentChat('computer-vision')`

### 2. **Backend Components**

#### a. **Agent Node** (`agents/wound_analyzer/agent.py`)
- **Main Function**: `wound_analyzer_agent(state: AgentState)`
- **Purpose**: Processes wound analysis requests and image data
- **Features**:
  - Receives user input and image metadata
  - Routes to severity router if urgent conditions detected
  - Integrates with vision APIs for image analysis
  - Provides structured medical assessment

#### b. **Service Functions** (`agents/wound_analyzer/service.py`)
- `validate_image_data()`: Validates image format and size
- `decode_base64_image()`: Decodes base64 image data
- `classify_wound_severity()`: Classifies wound severity level
- `build_wound_report()`: Formats analysis results
- `get_care_instructions()`: Provides wound care guides
- `check_infection_indicators()`: Detects infection signs

#### c. **Graph Integration** (`agents/graph/build_graph.py`)
- Node added to LangGraph workflow
- Registered in agent routing system
- Integrated with severity router for urgent cases

## How to Use

### 1. **Frontend Integration**
```javascript
// Create a wound analyzer chat
window.chatManager.createAgentChat('computer-vision')

// Send message with image
window.chatManager.sendMessage(messageText)

// Upload image via metadata
metadata: {
  image: {
    data: base64EncodedImage, // OR
    url: imageUrl
  }
}
```

### 2. **Backend Processing Flow**
```
User uploads image → Frontend sends to /chat/api/conversations/{id}/messages/add/
→ Django captures image metadata
→ Router identifies as wound_analyzer intent
→ wound_analyzer_agent processes image
→ Vision API analyzes image content
→ Returns formatted assessment
→ Routes to orientation if urgent
```

## Integration Points

### Message Payload
```python
{
  "role": "user",
  "content": "I have a cut on my finger",
  "metadata": {
    "image": {
      "data": "base64_encoded_image_or_url"
    },
    "agent": "computer-vision"
  }
}
```

### State Variables
```python
state = {
  "user_input": "Describe the wound...",
  "metadata": {
    "image": {...},
    "wound_analysis": {
      "processed": True,
      "severity": "moderate",
      "type": "laceration"
    }
  },
  "messages": [...],
  "current_agent": "wound_analyzer",
  "next_agent": "orientation"  # if severe
}
```

## Vision API Integration (TODO)

### OpenAI GPT-4 Vision Integration
```python
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4-vision-preview",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyze this wound image..."},
                {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                }
            ]
        }
    ]
)
```

### Alternative: TensorFlow/PyTorch Models
- Medical image classification models
- Skin condition detection
- Wound type classification
- Severity assessment

## Supported Wound Types

1. **Cuts & Lacerations** - Clean breaks in skin
2. **Burns** - Thermal injury with severity levels
3. **Rashes** - Skin irritation and conditions
4. **Abrasions** - Surface skin removal
5. **Wounds** - General puncture or traumatic wounds
6. **Surgical Wounds** - Post-operative care assessment

## Safety Features

### Automatic Escalation
The agent routes to the orientation agent if it detects:
- Severe bleeding
- Signs of infection
- Deep wounds with exposed tissue
- Thermal or chemical burns
- Widespread rashes with systemic symptoms

### Emergency Keywords
- "emergency", "severe", "urgent"
- "hospital", "infection"
- "uncontrolled bleeding"

## Requirements

### Python Packages
```txt
openai>=1.3.0          # GPT-4 Vision API
pillow>=10.0.0         # Image processing
numpy>=1.24.0          # Numerical operations
scikit-image>=0.20.0   # Image analysis
opencv-python>=4.8.0   # Computer vision
langgraph>=0.0.15      # Graph framework
```

### Environment Variables
```bash
OPENAI_API_KEY=your_api_key_here
```

## Testing

### Manual Testing
```python
# Test from Django shell
python manage.py shell

from agents.wound_analyzer.agent import wound_analyzer_agent
from agents.state import AgentState

state = AgentState(
    user_input="I have a deep cut on my hand",
    metadata={"image": {"data": base64_image}}
)

result = wound_analyzer_agent(state)
print(result["agent_output"])
```

### API Testing
```bash
curl -X POST http://localhost:8000/chat/api/conversations/1/messages/add/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: token" \
  -d '{
    "role": "user",
    "content": "Analyze this wound",
    "metadata": {"image": {"data": "base64_encoded_image"}}
  }'
```

## File Structure
```
agents/wound_analyzer/
├── __init__.py              # Package initialization
├── agent.py                 # Main agent implementation
├── service.py               # Service functions
├── requirements.txt         # Dependencies
└── README.md               # This file
```

## Configuration

### Image Constraints
- **Max Size**: 20MB
- **Supported Formats**: JPEG, PNG, WebP, GIF
- **Resolution**: 224x224 minimum recommended
- **Orientation**: Auto-detect and correct

### Response Format
```json
{
  "wound_type": "laceration",
  "severity": "moderate",
  "infection_risk": false,
  "care_instructions": [...],
  "emergency_signs": [...],
  "recommendation": "Clean and monitor"
}
```

## Known Limitations

1. **Image Quality**: Requires clear, well-lit images
2. **Privacy**: All images should be anonymized
3. **Accuracy**: AI analysis is for guidance, not diagnosis
4. **Compliance**: Ensure HIPAA compliance for patient data
5. **API Costs**: Vision API calls have associated costs

## Future Enhancements

- [ ] Real-time wound healing tracking
- [ ] Integration with dermatology databases
- [ ] Multi-language support
- [ ] Wound measurement capabilities
- [ ] Telemedicine integration
- [ ] Historical comparison tracking
- [ ] Custom wound care protocols

## Related Agents

- **Orientation Agent**: For facility recommendations
- **Triage Agent**: For emergency assessment
- **Medical Q&A Agent**: For general health questions
- **Mental Health Agent**: For psychological support

## Support

For issues or questions:
1. Check agent logs in `/agents/logs/`
2. Review error messages in console
3. Validate image format and encoding
4. Ensure API keys are configured

## License

This agent is part of the Sahatek platform and follows the same license terms.

---

**Created**: 2025-01-01
**Last Updated**: 2025-01-01
**Version**: 1.0.0
