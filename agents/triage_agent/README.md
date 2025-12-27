# Triage Agent Integration - LangGraph

## Overview
The Triage Agent has been integrated into the LangGraph framework, combining the functionality from `triage/logic.py` with the multi-agent orchestration system.

## Architecture

### File Structure
```
agents/
├── triage_agent/
│   ├── __init__.py
│   └── agent.py          # Main triage agent implementation
├── graph/
│   └── build_graph.py    # Updated to include triage_agent
└── ...
```

### Core Components

#### 1. **State Management** (`TriageAgentState`)
Extends the base `AgentState` with triage-specific fields:

```python
class TriageAgentState(TypedDict):
    # Base fields (from AgentState)
    user_input: str
    agent_output: Optional[str]
    current_agent: str
    next_agent: Optional[str]
    metadata: Dict[str, Any]
    messages: List[Dict[str, str]]
    
    # Triage-specific fields
    session_id: Optional[str]
    symptoms: List[str]
    age_group: Optional[str]
    diagnoses: List[Dict[str, Any]]
    healthcare_recommendation: Optional[Dict[str, Any]]
    nearby_facilities: List[Dict[str, Any]]
    user_location: Optional[tuple]
    extraction_result: Optional[Dict[str, Any]]
    diagnosis_result: Optional[Dict[str, Any]]
    confidence_score: float
    severity: Optional[str]
```

#### 2. **Client Initialization**
The agent manages initialization of required clients:
- **HTTP Client**: For API communication
- **Geolocator**: For location-based facility search
- **Symptom Extractor**: NER model from `triage/models/`
- **LLM Client**: Groq or OpenAI for healthcare recommendations

#### 3. **Core Functions**

##### `extract_symptoms(state)` 
- Extracts symptoms from user input using NER model
- Falls back to simple parsing if model unavailable
- Returns list of canonical symptoms

##### `start_diagnosis(state)`
- Creates/updates diagnostic session
- Initializes session data structure
- Determines age group from metadata

##### `generate_diagnosis(state)`
- Calls diagnosis model from `triage.diag.model`
- Generates list of potential diagnoses with confidence scores
- Updates session state with turn counter

##### `recommend_care(state)`
- Recommends appropriate healthcare service (PHARMACY, DOCTOR, HOSPITAL, etc.)
- Uses rule-based logic for common conditions
- Falls back to LLM for complex cases
- Finds nearby facilities if location provided

##### `triage_agent(state)` - Main Agent
- Orchestrates all sub-functions
- Manages state updates through the workflow
- Handles errors gracefully

## Usage in LangGraph

### Integration in Build Graph
The triage agent is now fully integrated in `agents/graph/build_graph.py`:

```python
# Import the agent
from agents.triage_agent.agent import triage_agent

# Add to graph
graph.add_node("triage", triage_agent)

# Route to it from router
graph.add_conditional_edges(
    "router",
    gatekeeper_routing_decision,
    {"triage": "triage", ...}
)
```

### Example Usage

```python
from agents.graph.build_graph import app

# Input state
state = {
    "user_input": "I have fever, cough, and sore throat",
    "intent": None,
    "messages": [],
    "current_agent": None,
    "next_agent": None,
    "agent_output": None,
    "metadata": {
        "age": "32",
        "location": "36.8065,10.1686"  # lat, lon
    }
}

# Execute
result = app.invoke(state)

# Output includes:
# - symptoms: ["fever", "cough", "sore throat"]
# - diagnoses: [{"name": "flu", "confidence": 0.85, ...}, ...]
# - healthcare_recommendation: {"service_type": "PHARMACY", "immediate_care": False}
# - nearby_facilities: [{"name": "Pharmacy X", "distance": 0.5, ...}, ...]
```

## Dependencies

### From triage/ module:
- `triage.src.extractor.SymptomExtractor` - NER symptom extraction
- `triage.diag.model.generate_diagnosis()` - Diagnosis generation
- `triage.diag.model.normalize_symptom()` - Symptom normalization
- `triage.diag.model.determine_age_group()` - Age group determination

### External libraries:
- `groq` - For LLM recommendations
- `openai` - Fallback LLM
- `geopy` - For location geocoding and distance calculation
- `httpx` - For Overpass API calls
- `langchain_community` - Vector stores (Chroma) - optional

## Configuration

Environment variables:
```bash
HEALTHCARE_API_KEY=sk-...
HEALTHCARE_BASE_URL=https://tokenfactory.esprit.tn/api
GROQ_API_KEY=gsk_...
```

## Error Handling

The agent includes comprehensive error handling:
- Graceful fallbacks if model files missing
- Attempts multiple LLM client options
- Safe defaults for recommendations
- Detailed logging for debugging

## Session Management

Diagnostic sessions are stored in memory (`diagnostic_sessions` dict):
```python
{
    "session_id": {
        "positive_symptoms": [...],
        "negative_symptoms": [...],
        "negative_diseases": set(),
        "asked_symptoms": set(),
        "user_age_group": "adult",
        "turn": 0,
        "previous_conf": {},
        "expand_search": False
    }
}
```

**Note**: For production, migrate session storage to Redis or database.

## Integration with Medical Agent

Both agents work together in the multi-agent system:
- **Router** decides intent (medical_qa vs triage)
- **Triage Agent** handles urgent symptom analysis
- **Medical Agent** answers general medical questions
- **Delegation** possible between agents based on registry rules

## Next Steps

1. **Database Migration**: Move `diagnostic_sessions` to persistent storage
2. **Testing**: Add unit tests for each sub-function
3. **Caching**: Implement caching for diagnosis results
4. **Performance**: Optimize NER model loading and API calls
5. **Monitoring**: Add metrics collection for accuracy tracking
