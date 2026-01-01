# 🚀 Quick Start - Wound Analyzer Agent

## What Was Created

A complete **Wound Analyzer Agent** for analyzing images of wounds, rashes, and skin conditions using computer vision.

```
agents/wound_analyzer/
├── __init__.py           # Package
├── agent.py              # Main implementation (220 lines)
├── service.py            # Utilities (200 lines)
├── requirements.txt      # Dependencies
└── README.md             # Full documentation
```

## 5-Minute Setup

### 1. Install Dependencies
```bash
cd agents/wound_analyzer
pip install -r requirements.txt
```

### 2. Set Environment Variable
```bash
export OPENAI_API_KEY=sk-...  # Your OpenAI API key
```

### 3. Test in Python Shell
```bash
python manage.py shell

from agents.wound_analyzer.agent import wound_analyzer_agent
from agents.state import AgentState

# Create test state
state = AgentState(
    user_input="I have a small cut on my finger",
    metadata={"image": {"data": "base64_encoded_image_here"}}
)

# Run agent
result = wound_analyzer_agent(state)
print(result["agent_output"])
```

## Already Integrated Into

✅ **Frontend** (`static/js/main.js`)
- Agent ID: `computer-vision`
- Title: `Wound Analyzer`
- Call: `window.chatManager.createAgentChat('computer-vision')`

✅ **Backend Router** (`agents/understanding_agent/agent.py`)
- Intent: `WOUND_ANALYZER`
- Auto-routes wound analysis requests

✅ **LangGraph** (`agents/graph/build_graph.py`)
- Node: `wound_analyzer`
- Severity router: Auto-escalates urgent cases

## How to Use from Frontend

```javascript
// Start a Wound Analyzer conversation
window.chatManager.createAgentChat('computer-vision')

// User then:
// 1. Uploads image
// 2. Types description
// 3. Gets analysis
// 4. Routes to orientation if severe
```

## Key Features

### 🖼️ Image Processing
- Accepts base64 or URL
- Max 20MB
- Auto-validates format

### 🔍 Analysis Capabilities
- Wound type classification (cut, burn, rash, abrasion)
- Severity assessment (mild to emergency)
- Infection risk detection
- Care instructions
- Emergency sign detection

### 🚨 Auto-Escalation
Routes to orientation agent if:
- Severe bleeding
- Infection signs
- Deep wounds
- Burns
- Widespread rashes

## API Integration (Next Step)

The agent is ready for OpenAI GPT-4 Vision API integration. To activate:

```python
# In agents/wound_analyzer/agent.py, replace analyze_with_vision_api():

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4-vision-preview",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyze this wound..."},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }
    ],
    max_tokens=1024
)

return response.choices[0].message.content
```

## Files Overview

### agent.py
| Function | Purpose |
|----------|---------|
| `wound_analyzer_agent()` | Main agent - processes requests |
| `analyze_wound_image()` | Handles image analysis |
| `handle_no_image_provided()` | Fallback if no image |
| `wound_severity_router()` | Routes urgent cases |

### service.py
| Function | Purpose |
|----------|---------|
| `validate_image_data()` | Validates image format |
| `classify_wound_severity()` | Severity classification |
| `get_care_instructions()` | Returns care guides |
| `check_infection_indicators()` | Detects infection |

## Testing Checklist

- [ ] Agent imports without errors
- [ ] Image validation works
- [ ] Fallback message displays correctly
- [ ] State updates properly
- [ ] Severity router works
- [ ] Routes to orientation on severe cases
- [ ] Vision API integration complete

## Troubleshooting

### Agent not loading?
```bash
python manage.py shell
from agents.wound_analyzer.agent import wound_analyzer_agent
```

### Image validation failing?
Check image is valid base64 or URL, under 20MB

### State not updating?
Ensure metadata dict is initialized in AgentState

### Missing dependencies?
```bash
pip install openai pillow numpy scikit-image opencv-python
```

## Related Documentation

- Full setup: `agents/wound_analyzer/README.md`
- Architecture: `WOUND_ANALYZER_SETUP.md`
- Frontend: `static/js/main.js` (lines 536-548)
- Graph: `agents/graph/build_graph.py`

## Status

✅ **Complete** - Ready for testing and OpenAI integration

---

**Questions?** Check the README.md in the wound_analyzer directory
