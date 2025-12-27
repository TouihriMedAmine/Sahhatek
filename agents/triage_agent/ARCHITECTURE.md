# Triage Workflow - Complete Architecture Explanation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Node-by-Node Explanation](#node-by-node-explanation)
4. [State Management](#state-management)
5. [Data Flow](#data-flow)
6. [Integration with LangGraph](#integration-with-langgraph)
7. [Examples](#examples)
8. [Error Handling](#error-handling)

---

## Overview

The triage workflow is a **4-node pipeline** that processes user symptoms and recommends appropriate healthcare facilities. It's designed as a modular LangGraph workflow where each node has a specific responsibility.

### High-Level Flow

```
User Input → Extraction → Diagnosis → Triage → Orientation → Final Recommendation
```

**What happens at each step:**
1. **Extraction**: Extracts symptoms from natural language input
2. **Diagnosis**: Identifies the disease/condition (placeholder - add your logic)
3. **Triage**: Determines what type of facility is needed
4. **Orientation**: Finds the nearest facility of that type

---

## Architecture

### Node Structure

Each node follows this pattern:
- **Input**: Reads from `state` dictionary
- **Processing**: Performs its specific task
- **Output**: Returns updated `state` dictionary with new fields

### LangGraph Integration

The nodes are connected in a linear chain:

```python
graph.add_edge("extraction", "diagnosis")
graph.add_edge("diagnosis", "triage")
graph.add_edge("triage", "orientation")
```

### State Object

All nodes share a common `AgentState` object that gets passed between them:

```python
class AgentState(TypedDict, total=False):
    # User input
    user_input: str
    user_location: tuple  # (latitude, longitude)
    
    # Extraction results
    symptoms: List[str]
    negative_symptoms: List[str]
    
    # Diagnosis results
    disease: str
    severity: str
    confidence: float
    
    # Triage results
    service_type: str  # HOSPITAL, PHARMACY, etc.
    immediate_care: bool
    
    # Orientation results
    nearby_facilities: List[Dict]
    selected_facility: Dict
    
    # Control flow
    should_end: bool
    agent_output: str
```

---

## Node-by-Node Explanation

### 1. Extraction Node (`extraction_node`)

**Purpose**: Extract symptoms from free-text user input using Named Entity Recognition (NER).

**Location**: `agents/triage_agent/nodes.py`

#### How It Works

1. **Input Processing**
   ```python
   user_input = "I have a headache, fever, but no nausea"
   ```

2. **NER Model**
   - Uses a spaCy-based NER model trained on medical symptoms
   - Model location: `triage/models/symptom_ner_spacy`
   - Identifies symptom entities in the text

3. **Symptom Normalization**
   - Converts extracted symptoms to canonical forms
   - Uses symptom dictionary: `triage/data/symptom_dict.json`
   - Example: "headache" → "headache", "head pain" → "headache"

4. **Negation Detection**
   - Detects negated symptoms (e.g., "no nausea", "don't have fever")
   - Uses spaCy's dependency parsing to identify negation
   - Separates positive and negative symptoms

5. **Output**
   ```python
   {
       "symptoms": ["headache", "fever"],  # Positive symptoms
       "negative_symptoms": ["nausea"],    # Negated symptoms
       "extraction_result": {...}          # Full NER result
   }
   ```

#### Code Flow

```python
def extraction_node(state):
    # 1. Get user input
    user_input = state.get("user_input", "")
    
    # 2. Initialize symptom extractor (NER model)
    extractor = get_symptom_extractor()
    
    # 3. Extract positive symptoms
    result = extractor.extract(user_input)
    positive_symptoms = [s.get('canonical') for s in result.get('symptoms', [])]
    
    # 4. Extract negative symptoms using negation detection
    negative_symptoms = detect_negation_with_spacy(user_input)
    
    # 5. Return updated state
    return {
        "symptoms": positive_symptoms,
        "negative_symptoms": negative_symptoms
    }
```

#### Example

**Input:**
```python
state = {
    "user_input": "I have a headache and fever, but no nausea or dizziness"
}
```

**Output:**
```python
{
    "symptoms": ["headache", "fever"],
    "negative_symptoms": ["nausea", "dizziness"]
}
```

---

### 2. Diagnosis Node (`diagnosis_node`)

**Purpose**: Identify the disease/condition from symptoms. **This is a placeholder - add your diagnosis logic here.**

**Location**: `agents/triage_agent/nodes.py`

#### How It Works (Current - Placeholder)

Currently returns placeholder values. You should replace this with your diagnosis model.

**Expected Input:**
```python
{
    "symptoms": ["headache", "fever"],
    "negative_symptoms": ["nausea"]
}
```

**Expected Output:**
```python
{
    "disease": "flu",           # Disease name
    "severity": "moderate",      # mild, moderate, or severe
    "confidence": 0.85          # 0.0 to 1.0
}
```

#### How to Add Your Diagnosis Logic

Replace the placeholder in `diagnosis_node()`:

```python
def diagnosis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    symptoms = state.get("symptoms", [])
    negative_symptoms = state.get("negative_symptoms", [])
    
    # TODO: Add your diagnosis model here
    # Example:
    # from your_diagnosis_module import diagnose
    # result = diagnose(symptoms, negative_symptoms)
    
    return {
        "disease": result["disease"],
        "severity": result["severity"],
        "confidence": result["confidence"]
    }
```

#### Example

**Input:**
```python
{
    "symptoms": ["headache", "fever", "fatigue"],
    "negative_symptoms": ["nausea"]
}
```

**Output (placeholder):**
```python
{
    "disease": "unknown",
    "severity": "moderate",
    "confidence": 0.5
}
```

---

### 3. Triage Node (`triage_node`)

**Purpose**: Determine what type of healthcare facility is needed based on disease and severity.

**Location**: `agents/triage_agent/nodes.py`

#### How It Works

1. **Input Processing**
   - Receives `disease` and `severity` from diagnosis node
   - Can also accept format: `"disease,severity"` string
   - Can receive mental health recommendation: `"emergency"` or `"therapist"`

2. **Rule-Based Recommendations**
   - First checks against hardcoded rules:
     - Common viral illnesses (flu, cold) + mild → `STAY_HOME`
     - Common viral illnesses + moderate/severe → `PHARMACY`
     - Minor conditions → `PHARMACY`
   - Falls back to LLM if no rule matches

3. **LLM-Based Recommendations**
   - Uses Groq API (or OpenAI) to determine facility type
   - Prompt: "Recommend healthcare service for {disease} with {severity} severity"
   - Returns format: `SERVICE_TYPE|IMMEDIATE_CARE`
   - Example: `HOSPITAL|YES` or `PHARMACY|NO`

4. **Service Types**
   - `HOSPITAL`: Serious/life-threatening conditions
   - `PHARMACY`: Minor conditions treatable with OTC meds
   - `CLINIC`: Moderate conditions requiring professional evaluation
   - `URGENT_CARE`: Urgent but not life-threatening
   - `PSYCHIATRIST`: Mental health conditions
   - `STAY_HOME`: Mild, self-limiting conditions

5. **Output**
   ```python
   {
       "service_type": "PHARMACY",
       "immediate_care": False,
       "recommendation_text": "Visit pharmacy for medication"
   }
   ```

#### Code Flow

```python
def triage_node(state):
    # 1. Get disease and severity
    disease = state.get("disease", "")
    severity = state.get("severity", "")
    
    # 2. Check for mental health input
    if state.get("mental_health_recommendation"):
        return handle_mental_health(state)
    
    # 3. Check rule-based recommendations
    if is_common_viral_illness(disease) and severity == "mild":
        return {"service_type": "STAY_HOME", ...}
    
    # 4. Use LLM for other cases
    recommendation = get_healthcare_recommendation(disease, severity)
    
    return {
        "service_type": recommendation["service_type"],
        "immediate_care": recommendation["immediate_care"]
    }
```

#### Example

**Input:**
```python
{
    "disease": "flu",
    "severity": "moderate"
}
```

**Output:**
```python
{
    "service_type": "PHARMACY",
    "immediate_care": False,
    "recommendation_text": "Visit pharmacy for medication"
}
```

**Another Example:**

**Input:**
```python
{
    "disease": "chest pain",
    "severity": "severe"
}
```

**Output:**
```python
{
    "service_type": "HOSPITAL",
    "immediate_care": True,
    "recommendation_text": "HOSPITAL|YES"
}
```

---

### 4. Orientation Node (`orientation_node`)

**Purpose**: Find the nearest healthcare facility based on triage recommendation.

**Location**: `agents/triage_agent/nodes.py`

#### How It Works

1. **Input Processing**
   - Receives `service_type` from triage node
   - Gets user location: `user_location` (lat, lon) or `user_input_location` (string)
   - Can receive mental health recommendation directly

2. **Location Geocoding**
   - If location string provided, geocodes it using Nominatim
   - Example: "Tunis, Tunisia" → (36.8065, 10.1815)

3. **STAY_HOME Handling**
   - If `service_type == "STAY_HOME"`, returns message without searching
   - No facility search needed

4. **Facility Search**
   - Uses Overpass API (OpenStreetMap) to find nearby facilities
   - Maps service types to OSM amenity tags:
     - `PHARMACY` → `amenity=pharmacy`
     - `HOSPITAL` → `amenity=hospital`
     - `CLINIC` → `amenity=clinic`
     - `PSYCHIATRIST` → searches hospitals/clinics
   - Searches within 5km radius
   - Sorts by distance (nearest first)
   - Returns top 5 facilities

5. **Facility Data Structure**
   ```python
   {
       "name": "Pharmacie Centrale",
       "type": "pharmacy",
       "distance": 0.5,  # km
       "latitude": 36.8070,
       "longitude": 10.1820,
       "address": "123 Main Street"
   }
   ```

6. **Output Formatting**
   - Formats user-friendly message with:
     - Facility name
     - Distance
     - Address (if available)
     - Immediate care warning (if needed)

7. **Output**
   ```python
   {
       "service_type": "PHARMACY",  # Preserved from triage
       "immediate_care": False,     # Preserved from triage
       "nearby_facilities": [...],  # List of all found facilities
       "selected_facility": {...},  # Nearest facility
       "should_end": True,
       "agent_output": "Found 5 nearby pharmacy facilities..."
   }
   ```

#### Code Flow

```python
def orientation_node(state):
    # 1. Get service type
    service_type = state.get("service_type", "")
    
    # 2. Handle STAY_HOME
    if service_type == "STAY_HOME":
        return {"agent_output": "Stay home and rest..."}
    
    # 3. Get user location
    lat, lon = get_user_location(state)
    
    # 4. Search for facilities
    facilities = find_nearby_facilities(lat, lon, service_type)
    
    # 5. Select nearest
    selected = facilities[0] if facilities else None
    
    # 6. Format output
    return {
        "selected_facility": selected,
        "nearby_facilities": facilities,
        "agent_output": format_output(selected)
    }
```

#### Example

**Input:**
```python
{
    "service_type": "PHARMACY",
    "user_location": (36.8065, 10.1815),
    "immediate_care": False
}
```

**Output:**
```python
{
    "service_type": "PHARMACY",
    "immediate_care": False,
    "nearby_facilities": [
        {
            "name": "Pharmacie Centrale",
            "distance": 0.5,
            "latitude": 36.8070,
            "longitude": 10.1820,
            "address": "123 Main Street"
        },
        # ... 4 more facilities
    ],
    "selected_facility": {
        "name": "Pharmacie Centrale",
        "distance": 0.5,
        ...
    },
    "agent_output": "Found 5 nearby pharmacy facilities.\n\n📍 **Nearest:** Pharmacie Centrale\n📏 **Distance:** 0.5 km"
}
```

---

## State Management

### State Flow Through Nodes

The state object flows through all nodes, with each node adding/modifying fields:

```python
# Initial state (from router)
state = {
    "user_input": "I have a headache and fever",
    "user_location": (36.8065, 10.1815)
}

# After extraction_node
state = {
    "user_input": "I have a headache and fever",
    "user_location": (36.8065, 10.1815),
    "symptoms": ["headache", "fever"],        # ← Added
    "negative_symptoms": []                     # ← Added
}

# After diagnosis_node
state = {
    "user_input": "I have a headache and fever",
    "user_location": (36.8065, 10.1815),
    "symptoms": ["headache", "fever"],
    "negative_symptoms": [],
    "disease": "flu",                          # ← Added
    "severity": "moderate",                    # ← Added
    "confidence": 0.85                         # ← Added
}

# After triage_node
state = {
    "user_input": "I have a headache and fever",
    "user_location": (36.8065, 10.1815),
    "symptoms": ["headache", "fever"],
    "negative_symptoms": [],
    "disease": "flu",
    "severity": "moderate",
    "confidence": 0.85,
    "service_type": "PHARMACY",                # ← Added
    "immediate_care": False,                   # ← Added
    "recommendation_text": "Visit pharmacy..." # ← Added
}

# After orientation_node
state = {
    "user_input": "I have a headache and fever",
    "user_location": (36.8065, 10.1815),
    "symptoms": ["headache", "fever"],
    "negative_symptoms": [],
    "disease": "flu",
    "severity": "moderate",
    "confidence": 0.85,
    "service_type": "PHARMACY",
    "immediate_care": False,
    "recommendation_text": "Visit pharmacy...",
    "nearby_facilities": [...],                # ← Added
    "selected_facility": {...},                # ← Added
    "should_end": True,                        # ← Added
    "agent_output": "Found 5 nearby..."        # ← Added
}
```

### State Preservation

Each node preserves important fields from previous nodes:
- `orientation_node` preserves `service_type` and `immediate_care` from `triage_node`
- All nodes preserve `user_input` and `user_location`

---

## Data Flow

### Complete Flow Diagram

```
┌─────────────┐
│   Router    │  Routes user to triage workflow
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Extraction │  Extracts symptoms from text
│    Node     │  Input: "I have headache and fever"
└──────┬──────┘  Output: symptoms=["headache", "fever"]
       │
       ▼
┌─────────────┐
│  Diagnosis  │  Identifies disease
│    Node     │  Input: symptoms=["headache", "fever"]
└──────┬──────┘  Output: disease="flu", severity="moderate"
       │
       ▼
┌─────────────┐
│   Triage    │  Determines facility type
│    Node     │  Input: disease="flu", severity="moderate"
└──────┬──────┘  Output: service_type="PHARMACY"
       │
       ▼
┌─────────────┐
│ Orientation │  Finds nearest facility
│    Node     │  Input: service_type="PHARMACY", location=(lat, lon)
└──────┬──────┘  Output: selected_facility={...}
       │
       ▼
┌─────────────┐
│     END     │  Returns final recommendation
└─────────────┘
```

### Mental Health Flow

```
┌─────────────┐
│   Mental    │  Processes mental health input
│   Health    │  Sets mental_health_recommendation="emergency"
│    Agent    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Orientation │  Handles mental health directly
│    Node     │  Sets service_type="PSYCHIATRIST"
└──────┬──────┘  Finds psychiatric facilities
       │
       ▼
┌─────────────┐
│     END     │
└─────────────┘
```

---

## Integration with LangGraph

### Graph Definition

```python
from langgraph.graph import StateGraph
from agents.state import AgentState

graph = StateGraph(AgentState)

# Add nodes
graph.add_node("extraction", extraction_node)
graph.add_node("diagnosis", diagnosis_node)
graph.add_node("triage", triage_node)
graph.add_node("orientation", orientation_node)

# Chain nodes
graph.add_edge("extraction", "diagnosis")
graph.add_edge("diagnosis", "triage")
graph.add_edge("triage", "orientation")

# End after orientation
graph.add_conditional_edges("orientation", lambda s: END, {END: END})

# Compile
app = graph.compile()
```

### Router Integration

The router can route to the triage workflow:

```python
def router_agent(state):
    if is_triage_intent(state["user_input"]):
        state["next_agent"] = "extraction"  # Start triage workflow
    return state
```

### Invocation

```python
initial_state = {
    "user_input": "I have a headache and fever",
    "user_location": (36.8065, 10.1815),
    "messages": [],
    "agent_registry": {...}
}

result = app.invoke(initial_state)
print(result["agent_output"])
```

---

## Examples

### Example 1: Simple Symptom Flow

**User Input:**
```
"I have a headache, fever, and I feel tired"
```

**Flow:**
1. **Extraction**: `["headache", "fever", "tiredness"]`
2. **Diagnosis**: `disease="flu", severity="moderate"`
3. **Triage**: `service_type="PHARMACY"`
4. **Orientation**: Finds nearest pharmacy (0.5 km away)

**Final Output:**
```
Found 5 nearby pharmacy facilities.

📍 **Nearest:** Pharmacie Centrale
📏 **Distance:** 0.5 km
📍 **Address:** 123 Main Street
```

### Example 2: Emergency Case

**User Input:**
```
"I have severe chest pain and difficulty breathing"
```

**Flow:**
1. **Extraction**: `["chest pain", "difficulty breathing"]`
2. **Diagnosis**: `disease="possible heart attack", severity="severe"`
3. **Triage**: `service_type="HOSPITAL", immediate_care=True`
4. **Orientation**: Finds nearest hospital (2.3 km away)

**Final Output:**
```
Found 3 nearby hospital facilities.

📍 **Nearest:** Hospital Central
📏 **Distance:** 2.3 km
📍 **Address:** 456 Medical Avenue

⚠️ **This requires immediate care - please seek help right away.**
```

### Example 3: Stay Home Case

**User Input:**
```
"I have a mild cold with runny nose"
```

**Flow:**
1. **Extraction**: `["runny nose"]`
2. **Diagnosis**: `disease="common cold", severity="mild"`
3. **Triage**: `service_type="STAY_HOME"`
4. **Orientation**: Skips facility search

**Final Output:**
```
Based on your symptoms, you can **stay home and rest**.

Your condition appears to be mild and self-limiting. 
Monitor your symptoms and seek medical care if they worsen.
```

### Example 4: Mental Health Flow

**User Input:**
```
"I need emergency mental health help"
```

**Flow:**
1. **Router**: Routes to mental health agent
2. **Mental Health Agent**: Sets `mental_health_recommendation="emergency"`
3. **Orientation**: Handles mental health directly, sets `service_type="PSYCHIATRIST"`
4. **Orientation**: Finds psychiatric facilities

**Final Output:**
```
Found 2 nearby mental health facilities.

📍 **Nearest:** Psychiatric Center
📏 **Distance:** 1.2 km

⚠️ **This requires immediate care - please seek help right away.**
```

---

## Error Handling

### Extraction Node Errors

**Error**: NER model not found
- **Fallback**: Simple text parsing (splits by commas)
- **Logs**: Warning message

**Error**: Symptom extractor initialization fails
- **Fallback**: Returns empty symptom lists
- **Logs**: Error message

### Diagnosis Node Errors

**Error**: Diagnosis model fails
- **Fallback**: Returns placeholder values (`disease="unknown"`)
- **Logs**: Error message

### Triage Node Errors

**Error**: LLM API connection fails
- **Fallback**: Rule-based recommendation (defaults to `DOCTOR`)
- **Logs**: Error message with retry attempts

**Error**: Invalid disease/severity
- **Fallback**: Defaults to `DOCTOR` with `immediate_care=False`
- **Logs**: Warning message

### Orientation Node Errors

**Error**: No location provided
- **Fallback**: Returns message asking for location
- **Logs**: Warning message

**Error**: Overpass API timeout (504)
- **Retry**: 2 attempts with 1 second delay
- **Fallback**: Returns empty facility list with error message
- **Logs**: Warning message

**Error**: Geocoding fails
- **Fallback**: Returns message asking for coordinates
- **Logs**: Warning message

**Error**: No facilities found
- **Fallback**: Returns message suggesting manual search
- **Logs**: Warning message

### State Preservation

All nodes preserve important state fields even on errors:
- `service_type` is preserved in `orientation_node` even if facility search fails
- `immediate_care` flag is preserved
- Previous node outputs are not lost

---

## Key Design Decisions

### 1. **Modular Node Design**
- Each node has a single responsibility
- Easy to test individually
- Easy to replace (e.g., diagnosis node)

### 2. **State-Based Communication**
- Nodes communicate through shared state object
- No direct function calls between nodes
- LangGraph handles state passing

### 3. **Fallback Strategies**
- Every node has fallback logic
- System degrades gracefully
- Never crashes completely

### 4. **Preservation of Important Fields**
- `service_type` and `immediate_care` preserved through orientation
- User location preserved throughout
- Previous node outputs available for debugging

### 5. **External API Handling**
- Retry logic for Overpass API
- Timeout handling
- Graceful degradation on API failures

---

## Testing

### Individual Node Testing

```python
from agents.triage_agent.nodes import extraction_node

state = {"user_input": "I have a headache"}
result = extraction_node(state)
print(result["symptoms"])  # ['headache']
```

### Full Workflow Testing

```python
from agents.graph.build_graph import app

state = {
    "user_input": "I have a headache and fever",
    "user_location": (36.8065, 10.1815)
}
result = app.invoke(state)
print(result["agent_output"])
```

### Test Script

Run the comprehensive test suite:

```bash
python agents/triage_agent/test_nodes.py
```

---

## Summary

The triage workflow is a **4-stage pipeline** that:

1. **Extracts** symptoms from natural language
2. **Diagnoses** the condition (placeholder - add your logic)
3. **Triages** to determine facility type
4. **Orients** by finding the nearest facility

Each stage is **modular**, **testable**, and has **fallback strategies**. The workflow integrates seamlessly with LangGraph and handles errors gracefully.

**Next Step**: Add your diagnosis logic to `diagnosis_node()` in `agents/triage_agent/nodes.py`!

