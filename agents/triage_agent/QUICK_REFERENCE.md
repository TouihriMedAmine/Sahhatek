# Triage Workflow - Quick Reference Guide

## 🚀 Quick Start

```python
from agents.graph.build_graph import app

state = {
    "user_input": "I have a headache and fever",
    "user_location": (36.8065, 10.1815),  # (lat, lon)
    "messages": [],
    "agent_registry": {}
}

result = app.invoke(state)
print(result["agent_output"])
```

## 📊 Flow Diagram

```
┌──────────────┐
│ User Input   │  "I have headache and fever"
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Extraction   │  → symptoms: ["headache", "fever"]
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Diagnosis    │  → disease: "flu", severity: "moderate"
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Triage       │  → service_type: "PHARMACY"
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Orientation  │  → Nearest pharmacy: 0.5 km away
└──────┬───────┘
       │
       ▼
   Final Output
```

## 🔧 Node Details

### 1. Extraction Node
- **Input**: `user_input` (string)
- **Output**: `symptoms`, `negative_symptoms` (lists)
- **What it does**: Extracts symptoms using NER model

### 2. Diagnosis Node
- **Input**: `symptoms`, `negative_symptoms`
- **Output**: `disease`, `severity`, `confidence`
- **What it does**: Identifies disease (ADD YOUR LOGIC HERE)

### 3. Triage Node
- **Input**: `disease`, `severity`
- **Output**: `service_type`, `immediate_care`
- **What it does**: Determines facility type needed
- **Service Types**: `HOSPITAL`, `PHARMACY`, `CLINIC`, `URGENT_CARE`, `PSYCHIATRIST`, `STAY_HOME`

### 4. Orientation Node
- **Input**: `service_type`, `user_location`
- **Output**: `selected_facility`, `nearby_facilities`
- **What it does**: Finds nearest facility

## 📝 State Fields

### Required Input
```python
{
    "user_input": str,           # User's symptom description
    "user_location": tuple,       # (latitude, longitude) - Optional
}
```

### After Extraction
```python
{
    "symptoms": List[str],        # Positive symptoms
    "negative_symptoms": List[str] # Negated symptoms
}
```

### After Diagnosis
```python
{
    "disease": str,               # Disease name
    "severity": str,             # "mild", "moderate", or "severe"
    "confidence": float          # 0.0 to 1.0
}
```

### After Triage
```python
{
    "service_type": str,         # Facility type
    "immediate_care": bool,      # True if urgent
    "recommendation_text": str   # Human-readable recommendation
}
```

### After Orientation
```python
{
    "selected_facility": dict,    # Nearest facility
    "nearby_facilities": list,    # All found facilities
    "should_end": True,
    "agent_output": str          # Final formatted message
}
```

## 🎯 Service Type Mapping

| Service Type | When Used | Example |
|-------------|-----------|---------|
| `STAY_HOME` | Mild, self-limiting conditions | Common cold, mild flu |
| `PHARMACY` | Minor conditions, OTC meds | Mild headache, allergies |
| `CLINIC` | Moderate conditions | Persistent symptoms |
| `URGENT_CARE` | Urgent but not emergency | High fever, injury |
| `HOSPITAL` | Serious/life-threatening | Chest pain, stroke |
| `PSYCHIATRIST` | Mental health conditions | Depression, anxiety |

## 🔄 Mental Health Flow

```python
# Mental health agent sets:
state["mental_health_recommendation"] = "emergency"  # or "therapist"

# Orientation node handles it:
# - "emergency" → PSYCHIATRIST + immediate_care=True
# - "therapist" → PSYCHIATRIST + immediate_care=False
```

## 🧪 Testing

### Test Individual Nodes
```python
from agents.triage_agent.nodes import extraction_node

state = {"user_input": "I have a headache"}
result = extraction_node(state)
print(result["symptoms"])  # ['headache']
```

### Test Full Workflow
```bash
python agents/triage_agent/test_nodes.py
```

## ⚠️ Common Issues

### Issue: No facilities found
- **Cause**: Overpass API timeout or no facilities in area
- **Solution**: Check location, increase radius, or use different location

### Issue: service_type is None
- **Cause**: State not properly merged between nodes
- **Solution**: Ensure each node returns all required fields

### Issue: Diagnosis returns placeholder
- **Cause**: Diagnosis node not implemented yet
- **Solution**: Add your diagnosis logic to `diagnosis_node()`

## 📚 Files

- `agents/triage_agent/nodes.py` - All node implementations
- `agents/triage_agent/workflow.py` - Complete workflow function
- `agents/graph/build_graph.py` - LangGraph configuration
- `agents/state.py` - State definition
- `agents/triage_agent/test_nodes.py` - Test script
- `agents/triage_agent/ARCHITECTURE.md` - Full documentation

## 🎓 Next Steps

1. **Add Diagnosis Logic**: Implement `diagnosis_node()` in `nodes.py`
2. **Test**: Run `python agents/triage_agent/test_nodes.py`
3. **Customize**: Adjust output formatting in each node
4. **Deploy**: Integrate with your main application

## 💡 Tips

- Always preserve `service_type` and `immediate_care` in orientation node
- Handle `STAY_HOME` case early in orientation node (no facility search)
- Use retry logic for external APIs (Overpass, geocoding)
- Log important state transitions for debugging
- Test each node individually before testing full flow

