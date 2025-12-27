# Triage Agent - Quick Start Guide

## Overview
The Triage Agent has been successfully integrated into the LangGraph multi-agent system. It combines symptom analysis, diagnosis generation, and healthcare recommendations.

## Quick Example

```python
from agents.graph.build_graph import app

# Define input state
state = {
    "user_input": "I have fever 38.5, severe headache, and body aches",
    "intent": None,
    "messages": [],
    "current_agent": None,
    "next_agent": None,
    "agent_output": None,
    "metadata": {
        "age": "32",
        "location": "36.8065,10.1686"  # Tunis coordinates (lat, lon)
    }
}

# Run through the agent system
result = app.invoke(state)

# Inspect results
print("Extracted Symptoms:", result.get("symptoms"))
print("Age Group:", result.get("age_group"))
print("Diagnoses:", result.get("diagnoses"))
print("Recommendation:", result.get("healthcare_recommendation"))
print("Nearby Facilities:", result.get("nearby_facilities"))
```

## Output Structure

```json
{
    "symptoms": ["fever", "headache", "body aches"],
    "age_group": "adult",
    "diagnoses": [
        {
            "name": "Influenza (Flu)",
            "confidence": 0.87,
            "symptoms": ["fever", "headache", "body aches"]
        },
        {
            "name": "Common Cold",
            "confidence": 0.45,
            "symptoms": ["fever", "headache"]
        }
    ],
    "healthcare_recommendation": {
        "service_type": "PHARMACY",
        "immediate_care": false,
        "recommendation_text": "OTC medication and rest recommended"
    },
    "nearby_facilities": [
        {
            "name": "Pharmacie Centrale",
            "type": "pharmacy",
            "distance": 0.5,
            "latitude": 36.8075,
            "longitude": 10.1695,
            "address": "Avenue Habib Bourguiba, Tunis"
        }
    ]
}
```

## Component Functions

### 1. Extract Symptoms
```python
from agents.triage_agent.agent import extract_symptoms

state = {"user_input": "I have a sore throat and cough"}
result = extract_symptoms(state)
print(result["symptoms"])  # ["sore throat", "cough"]
```

### 2. Start Diagnostic Session
```python
from agents.triage_agent.agent import start_diagnosis

state = {
    "user_input": "fever 39°C and chills",
    "metadata": {"age": "45"}
}
result = start_diagnosis(state)
print(result["session_id"])  # session_1734440123
print(result["symptoms"])    # ["fever", "chills"]
```

### 3. Generate Diagnosis
```python
from agents.triage_agent.agent import generate_diagnosis

# After starting diagnosis (session_id must exist)
result = generate_diagnosis(state)
print(result["diagnoses"])        # List of potential diagnoses
print(result["confidence_score"]) # 0.85
```

### 4. Recommend Care
```python
from agents.triage_agent.agent import recommend_care

result = recommend_care(state)
print(result["healthcare_recommendation"]["service_type"])  # "PHARMACY"
print(result["nearby_facilities"])  # List of nearby facilities
```

## Healthcare Service Types

| Type | Use Case | Examples |
|------|----------|----------|
| `STAY_HOME` | Self-limiting viral illnesses | Mild cold, mild flu |
| `PHARMACY` | Minor issues requiring OTC meds | Mild headache, allergy |
| `CLINIC` | Moderate issues | Persistent symptoms, chronic conditions |
| `DOCTOR` | Professional evaluation needed | Moderate pain, need prescription |
| `URGENT_CARE` | Urgent but not life-threatening | Severe pain, high fever, injury |
| `HOSPITAL` | Serious/life-threatening | Chest pain, difficulty breathing |
| `MENTAL_HEALTH` | Mental health crisis | Severe anxiety, suicidal ideation |

## Integration with Other Agents

The router automatically directs requests:

```
User Input
    ↓
Router (decides intent)
    ├─ "I have fever" → Triage Agent
    ├─ "What is diabetes?" → Medical QA Agent
    ├─ "I feel depressed" → Mental Health Agent
    └─ "Is garlic a cure-all?" → Rumor Detection Agent
```

## Environment Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
# In .env or export commands
export HEALTHCARE_API_KEY="sk-..."
export HEALTHCARE_BASE_URL="https://tokenfactory.esprit.tn/api"
export GROQ_API_KEY="gsk_..."
```

### 3. Ensure Model Files Exist
```
triage/
├── models/
│   └── symptom_ner_spacy/  # NER model for symptom extraction
├── diag/
│   ├── fast_medical_index.faiss
│   ├── full_medical_index.faiss
│   └── nhs_conditions2.json
└── data/
    └── symptom_dict.json
```

## Debugging

### Enable Detailed Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("agents.triage_agent.agent")
logger.setLevel(logging.DEBUG)
```

### Test Symptom Extraction
```python
from agents.triage_agent.agent import extract_symptoms

state = {"user_input": "I have fever and sore throat"}
result = extract_symptoms(state)
print(result["extraction_result"])  # See full extraction details
```

### Check Session State
```python
from agents.triage_agent.agent import diagnostic_sessions

print(diagnostic_sessions.keys())  # All active sessions
session = diagnostic_sessions.get("session_xyz")
print(session)  # Full session state
```

## Common Issues

### Issue: Symptom Extractor Not Loading
**Solution**: Check that `triage/models/symptom_ner_spacy/` exists. The agent will fallback to simple parsing.

### Issue: LLM Recommendations Failing
**Solution**: Ensure `GROQ_API_KEY` is set. Falls back to OpenAI if Groq fails.

### Issue: No Nearby Facilities Found
**Solution**: Check location coordinates are valid (lat: -90 to 90, lon: -180 to 180). Overpass API may be slow - it times out after 30s.

### Issue: Session Not Found
**Solution**: Sessions are stored in memory. In production, migrate to Redis/DB. Each session has an ID - use it to maintain state across requests.

## Advanced Usage

### Custom Session Management
```python
from agents.triage_agent.agent import diagnostic_sessions

# Create custom session
session_id = "custom_session_123"
diagnostic_sessions[session_id] = {
    "positive_symptoms": ["fever", "cough"],
    "negative_symptoms": [],
    "negative_diseases": set(),
    "asked_symptoms": {"fever", "cough"},
    "user_age_group": "adult",
    "turn": 0,
    "previous_conf": {},
    "expand_search": False
}

# Now use in state
state = {"session_id": session_id, ...}
result = generate_diagnosis(state)
```

### Location-Based Recommendations
```python
from agents.triage_agent.agent import geocode_location, find_nearby_facilities

# Geocode address
lat, lon = geocode_location("Tunis, Tunisia")

# Find facilities
facilities = find_nearby_facilities(lat, lon, "PHARMACY", radius_km=5)
for facility in facilities:
    print(f"{facility['name']} - {facility['distance']}km away")
```

## Production Deployment

### Recommended Changes:
1. **Session Storage**: Move from in-memory dict to Redis
   ```python
   import redis
   diagnostic_sessions = redis.Redis(host='localhost', port=6379)
   ```

2. **API Rate Limiting**: Add per-user throttling

3. **Caching**: Cache diagnosis results for common symptoms

4. **Monitoring**: Track:
   - Diagnosis accuracy (compare user feedback)
   - API response times
   - Error rates by component

5. **Fallback Strategies**: Implement graceful degradation if APIs fail

## References

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [Groq API](https://console.groq.com/docs/speech-text)
- [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API)
- [Geopy Documentation](https://geopy.readthedocs.io/)

## Support

For issues or questions:
1. Check logs: `logger.debug("message")`
2. Review `agents/triage_agent/README.md` for detailed docs
3. See `TRIAGE_INTEGRATION_SUMMARY.md` for architecture overview
