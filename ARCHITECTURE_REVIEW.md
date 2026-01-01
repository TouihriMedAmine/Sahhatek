# Wound Analyzer - Architecture & Code Review

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       USER BROWSER                               │
├─────────────────────────────────────────────────────────────────┤
│                     chat.html Interface                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  [Upload Button] ← Paperclip Icon                        │   │
│  │      ↓                                                    │   │
│  │  FileInput(accept="image/*")                             │   │
│  │      ↓                                                    │   │
│  │  FileReader.readAsDataURL() → base64                     │   │
│  │      ↓                                                    │   │
│  │  pendingImage = "data:image/jpeg;base64,/9j/..."        │   │
│  │      ↓                                                    │   │
│  │  User types message: "classify my wound"                 │   │
│  │      ↓                                                    │   │
│  │  sendMessage(content, imageData)                         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    REST API CALL                                 │
├─────────────────────────────────────────────────────────────────┤
│  POST /chat/api/conversations/7/messages/add/                   │
│  Content-Type: application/json                                 │
│  X-CSRFToken: [token]                                           │
│                                                                  │
│  Payload:                                                        │
│  {                                                              │
│    "role": "user",                                              │
│    "content": "classify my wound",                              │
│    "latitude": 36.7070497,                                      │
│    "longitude": 10.208099,                                      │
│    "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgAB..."      │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              DJANGO BACKEND (views.py)                           │
├─────────────────────────────────────────────────────────────────┤
│  def add_message(request, conversation_id):                     │
│    1. Parse JSON request body                                    │
│    2. Extract: image_data = data.get("image")                   │
│    3. Save Message with metadata                                │
│       └─ message_metadata["image"] = image_data                 │
│    4. Build LangGraph state                                     │
│       └─ metadata["image"] = image_data                         │
│    5. Invoke: result = app.invoke(langgraph_state)              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│          LANGGRAPH AGENT ORCHESTRATION                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐                                                 │
│  │   ROUTER   │  (understanding_agent.py)                       │
│  │            │  Lines 450-488                                  │
│  │ • Analyze: "classify my wound"                              │
│  │ • Detect: keyword "wound" found                             │
│  │ • Check: emergency keywords? No                             │
│  │ • Decision: Route to wound_analyzer                         │
│  │ • Confidence: 0.85                                          │
│  │ • next_agent = "wound_analyzer"                             │
│  └────────────┘                                                 │
│        ↓                                                         │
│  ┌────────────────┐                                             │
│  │ GATEKEEPER     │  (build_graph.py)                          │
│  │ (Routing)      │  Lines 155-206                             │
│  │                │                                              │
│  │ Check: next_agent == "wound_analyzer"? YES                  │
│  │ Priority list: [mental_health, medical_qa, rumor,           │
│  │                 wound_analyzer]  ← Found!                   │
│  │ Return: "wound_analyzer"                                    │
│  └────────────────┘                                             │
│        ↓                                                         │
│  ┌──────────────────────┐                                       │
│  │ WOUND ANALYZER AGENT │  (agent.py)                          │
│  │                      │  Lines 141-195                        │
│  │ • Extract metadata.image                                    │
│  │ • has_image? YES                                            │
│  │ • Call: analyze_wound_image()                               │
│  └──────────────────────┘                                       │
│        ↓                                                         │
│  ┌──────────────────────┐                                       │
│  │ IMAGE PROCESSING     │  (Lines 198-245)                     │
│  │                      │                                        │
│  │ • Extract base64     │                                       │
│  │ • Decode: base64 → bytes                                    │
│  │ • Validate: PIL.Image.verify()                              │
│  │ • Load: PIL.Image.open(BytesIO(bytes))                      │
│  │ • Convert: RGB mode                                         │
│  └──────────────────────┘                                       │
│        ↓                                                         │
│  ┌──────────────────────────────┐                               │
│  │ FASTAI MODEL INFERENCE       │  (Lines 248-310)            │
│  │                              │                               │
│  │ • Load model (ResNet34)      │                              │
│  │ • Load weights from .pth     │                              │
│  │ • Create PILImage tensor     │                              │
│  │ • Run: learner.predict()     │                              │
│  │ • Output:                    │                              │
│  │   - pred_class: "Laceration" │                              │
│  │   - probs: [0.001, ...]      │                              │
│  │   - confidence: 0.85         │                              │
│  └──────────────────────────────┘                               │
│        ↓                                                         │
│  ┌──────────────────────────────┐                               │
│  │ REPORT GENERATION            │  (Lines 351-458)            │
│  │                              │                               │
│  │ • Wound Type: Laceration     │                              │
│  │ • Severity: Moderate (2/4)   │                              │
│  │ • Confidence: 85%            │                              │
│  │ • Care Instructions:         │                              │
│  │   - Stop bleeding            │                              │
│  │   - Clean wound              │                              │
│  │   - May need stitches        │                              │
│  │ • Emergency Signs:           │                              │
│  │   - Won't stop bleeding      │                              │
│  │   - Edges won't stay together│                              │
│  │ • When to seek help          │                              │
│  └──────────────────────────────┘                               │
│        ↓                                                         │
│  ┌──────────────────────┐                                       │
│  │ WOUND ANALYZER       │  (build_graph.py)                   │
│  │ POST-PROCESSING      │  Lines 318-333                      │
│  │                      │                                        │
│  │ Check: needs_urgent_referral?                              │
│  │ YES → route to orientation                                 │
│  │ NO  → END conversation                                     │
│  └──────────────────────┘                                       │
│        ↓                                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              RESPONSE TO FRONTEND                                │
├─────────────────────────────────────────────────────────────────┤
│  agent_output = [Full Medical Report]                           │
│                                                                  │
│  Save Message:                                                   │
│  {                                                              │
│    role: "assistant",                                           │
│    content: "[Full Report]",                                    │
│    metadata: {                                                   │
│      agent_used: "wound_analyzer",                              │
│      wound_analysis: {...}                                      │
│    }                                                            │
│  }                                                              │
│                                                                  │
│  Return JSON:                                                    │
│  {                                                              │
│    success: true,                                               │
│    bot_message: {                                               │
│      content: "[Full Report]",                                  │
│      metadata: {...}                                            │
│    }                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              FRONTEND DISPLAY                                    │
├─────────────────────────────────────────────────────────────────┤
│  Chat bubble shows:                                              │
│                                                                  │
│  🩹 WOUND ANALYSIS REPORT                                       │
│  📋 Classification                                               │
│  - Wound Type: Laceration                                       │
│  - Severity: Moderate (Level 2/4)                               │
│  - AI Confidence: 85%                                           │
│  💊 Recommended Care                                            │
│  - Stop bleeding with pressure                                  │
│  - Clean thoroughly with soap and water                         │
│  - May need stitches                                            │
│  - Keep clean and dry                                           │
│  ⚠️ Emergency Signs                                             │
│  - Won't stop bleeding                                          │
│  - Edges won't stay together                                    │
│  - Possible nerve/tendon damage                                │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Code Structure Overview

```
PROJECT STRUCTURE
─────────────────

agents/
├── wound_analyzer/              ← NEW AGENT
│   ├── __init__.py
│   ├── agent.py                 (458 lines)
│   │   ├── CLASS_NAMES (10 types)
│   │   ├── BASE_SEVERITY (severity map)
│   │   ├── SEVERITY_LEVELS (0-4 scale)
│   │   ├── CARE_INSTRUCTIONS_MAP (8 fields × 10 types)
│   │   ├── wound_analyzer_agent() → Main entry
│   │   ├── analyze_wound_image() → Image processing
│   │   ├── infer_wound_classification() → ML inference
│   │   ├── load_wound_classifier_model() → Model loading
│   │   ├── build_wound_analysis_report() → Report gen
│   │   └── analyze_with_fallback() → Fallback mode
│   │
│   └── service.py               (437 lines)
│       ├── validate_image_data() → Size/format check
│       ├── decode_base64_image() → Base64 → bytes
│       ├── preprocess_image_for_fastai() → PIL prep
│       ├── classify_wound_severity() → Severity calc
│       ├── check_infection_indicators() → Infection risk
│       └── get_care_instructions() → Care gen
│
├── understanding_agent/
│   └── agent.py                 (740 lines)
│       ├── KEYWORDS_WOUND (60+ keywords)
│       ├── KEYWORDS_EMERGENCY (severe wound keywords)
│       ├── simple_understanding_agent()
│       ├── detect_wounds()        ← NEW (lines 450-488)
│       └── Intent.WOUND_ANALYZER  ← NEW
│
├── graph/
│   └── build_graph.py           (359 lines)
│       ├── wound_analyzer_agent_node() → Agent wrapper
│       ├── gatekeeper_routing_decision() → Router logic
│       │   └── Added: "wound_analyzer" to priority
│       ├── wound_analyzer_router() → Post-processing ← NEW
│       ├── graph.add_node("wound_analyzer", ...)
│       ├── graph.add_conditional_edges("router", ...)
│       │   └── Added: "wound_analyzer": "wound_analyzer"
│       ├── graph.add_conditional_edges("wound_analyzer", ...)
│       └── app = graph.compile()
│
└── views.py                     (1349 lines)
    ├── add_message()
    │   ├── image_data = data.get("image")     (line 168)
    │   ├── message_metadata["image"] = image_data (line 175)
    │   ├── langgraph_state["metadata"]["image"] (line 362)
    │   └── result = app.invoke(langgraph_state)

templates/
└── chat.html                    (3299 lines)
    ├── <button id="upload-btn-chat"> (line 761)
    ├── <input id="fileInput" accept="image/*"> (line 786)
    ├── let pendingImage = null (line 894)
    ├── uploadBtnChat.addEventListener('click', ...) (line 2332)
    ├── fileInput.addEventListener('change', ...) (line 2339)
    ├── async function addMessage(..., imageData) (line 945)
    │   └── payload.image = imageData
    ├── async function sendMessage(content) (line 1972)
    │   └── const imageToSend = pendingImage
    └── attachMessageHandlers()
```

---

## File Dependencies

```
DEPENDENCY GRAPH
────────────────

Frontend (chat.html)
  ↓
  └─→ POST /chat/api/conversations/{id}/messages/add/
      ↓
Django (views.py)
  ├─→ agents.graph.build_graph (import app)
  └─→ Message.objects.create(metadata={image: ...})
      ↓
LangGraph (build_graph.py)
  ├─→ agents.understanding_agent (router node)
  │   └─→ Detect wound keywords
  │       └─→ return Intent.WOUND_ANALYZER
  │
  ├─→ agents.wound_analyzer (wound_analyzer node)
  │   ├─→ agents.wound_analyzer.service
  │   │   ├─→ validate_image_data()
  │   │   ├─→ decode_base64_image()
  │   │   └─→ preprocess_image_for_fastai()
  │   │
  │   ├─→ fastai.vision.all (model inference)
  │   │   └─→ torch (GPU/CPU)
  │   │
  │   └─→ PIL/Pillow (image handling)
  │
  └─→ END (conditional routing)
```

---

## Key Functions with Line References

### Frontend (JavaScript)

| Function | File | Lines | Purpose |
|----------|------|-------|---------|
| `pendingImage` | chat.html | 894 | Global state for image |
| `uploadBtnChat.addEventListener` | chat.html | 2332 | Click handler |
| `fileInput.addEventListener` | chat.html | 2339 | Change handler |
| `FileReader.readAsDataURL()` | chat.html | 2354 | Encode to base64 |
| `addMessage()` | chat.html | 945 | API call with image |
| `sendMessage()` | chat.html | 1972 | Include pending image |

### Backend (Django)

| Function | File | Lines | Purpose |
|----------|------|-------|---------|
| `add_message()` | views.py | 150 | Extract image |
| `image_data = data.get("image")` | views.py | 168 | Get from request |
| `message_metadata["image"]` | views.py | 175 | Store metadata |
| `langgraph_state["metadata"]["image"]` | views.py | 362 | Pass to agents |

### Routing (LangGraph)

| Function | File | Lines | Purpose |
|----------|------|-------|---------|
| `detect_wounds()` | understanding_agent | 450-488 | Keyword detection |
| `gatekeeper_routing_decision()` | build_graph.py | 155-206 | Priority routing |
| `wound_analyzer_router()` | build_graph.py | 318-333 | Post-processing |

### ML/Analysis

| Function | File | Lines | Purpose |
|----------|------|-------|---------|
| `wound_analyzer_agent()` | agent.py | 141-195 | Entry point |
| `analyze_wound_image()` | agent.py | 198-245 | Main pipeline |
| `infer_wound_classification()` | agent.py | 248-310 | Model inference |
| `decode_base64_image()` | service.py | 50-73 | Decode image |
| `validate_image_data()` | service.py | 18-47 | Validate input |
| `build_wound_analysis_report()` | agent.py | 351-458 | Generate report |

---

## Data Structures

### Image Data Flow

```python
Frontend:
  string: "data:image/jpeg;base64,/9j/4AAQSkZJRgAB..."

Backend Request:
  Dict: {
    role: "user",
    content: "classify my wound",
    image: "data:image/jpeg;base64,/9j/4AAQSkZJRgAB...",
    latitude: 36.7070497,
    longitude: 10.208099
  }

Message Metadata:
  Dict: {
    "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgAB...",
    "latitude": 36.7070497,
    "longitude": 10.208099
  }

LangGraph State:
  Dict: {
    "user_input": "classify my wound",
    "metadata": {
      "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgAB...",
      "user_id": 123,
      "conversation_id": 7
    }
  }

Service Layer:
  Normalized: {
    "data": "/9j/4AAQSkZJRgABAQAAAQABAAD..." (no prefix)
  }

Processing:
  image_bytes: b'\xff\xd8\xff\xe0\x00\x10...' (binary)
  PIL Image: <PIL.Image.Image image mode=RGB size=512x512>
  Model Input: FastAI tensor (224x224 RGB)

Output:
  Prediction: ("Laceration", [0.001, ..., 0.85, ...])
  Report: String with formatted medical assessment
```

### Wound Analysis Metadata

```python
metadata["wound_analysis"] = {
    "processed": True,
    "wound_type": "Laceration",
    "confidence": 0.85,
    "severity_level": 2,
    "severity_text": "Moderate",
    "needs_urgent_referral": False,
    "care_instructions": [
        "Stop bleeding with pressure",
        "Clean thoroughly",
        "May need stitches",
        "Keep clean and dry"
    ],
    "emergency_signs": [
        "Won't stop bleeding",
        "Edges won't stay together",
        "Possible nerve/tendon damage"
    ]
}
```

---

## Error Handling

```python
Image Processing Pipeline:

1. Base64 Decode
   ├─ Success → image_bytes
   ├─ Error: Invalid base64
   │  └─ Return: (False, None, "Failed to decode...")
   └─ Fallback: analyze_with_fallback(user_input)

2. PIL Validation
   ├─ Success → PIL Image
   ├─ Error: Invalid image format
   │  └─ Return: (False, None, "Not a valid image...")
   └─ Fallback: analyze_with_fallback(user_input)

3. Model Loading
   ├─ Success → Learner with weights
   ├─ Error: Model not found
   │  └─ FASTAI_AVAILABLE = False
   └─ Fallback: analyze_with_fallback(user_input)

4. Inference
   ├─ Success → (pred_class, confidence)
   ├─ Error: Inference failed
   │  └─ except Exception
   └─ Fallback: analyze_with_fallback(user_input)

5. Fallback Response
   └─ "I'm running in fallback mode without the AI model..."
```

---

## Testing Points

### Frontend Testing
```javascript
// 1. Upload button exists and is clickable
document.getElementById('upload-btn-chat')

// 2. File input exists and accepts images
document.getElementById('fileInput')

// 3. FileReader works
new FileReader().readAsDataURL(file)

// 4. pendingImage is set
console.log(pendingImage)

// 5. API call includes image
JSON.stringify({image: pendingImage})
```

### Backend Testing
```python
# 1. Extract image from request
image_data = data.get("image")

# 2. Image in message metadata
message.metadata["image"]

# 3. Image in LangGraph state
langgraph_state["metadata"]["image"]

# 4. Wound detection
"wound" in "classify my wound"  # True

# 5. Router priority
"wound_analyzer" in priority_list  # True
```

### ML Testing
```python
# 1. Base64 decoding
is_valid, image_bytes, error = decode_base64_image(base64_str)

# 2. PIL Image creation
img = Image.open(BytesIO(image_bytes))

# 3. Model loading
learner = load_wound_classifier_model()

# 4. Inference
pred_class, _, probs = learner.predict(PILImage.create(img))

# 5. Report generation
report = build_wound_analysis_report(...)
```

---

## Conclusion

The **Wound Analyzer is fully integrated** into the Sahhatek system with:

✅ **Frontend**: Complete upload UI with event handlers
✅ **API**: Image extraction and metadata storage
✅ **Routing**: Wound detection and priority routing
✅ **ML**: FastAI model integration with fallback
✅ **Reporting**: Professional medical assessment generation
✅ **Error Handling**: Graceful degradation at each step
✅ **Integration**: Seamless LangGraph orchestration

**System Status**: 🟢 **PRODUCTION READY**

