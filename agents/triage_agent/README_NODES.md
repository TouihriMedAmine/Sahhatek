# Triage Workflow - Node-Based Architecture

This document describes the new node-based triage workflow integrated into LangGraph.

## Overview

The triage workflow has been restructured into 4 separate nodes that chain together:

1. **Extraction Node** - Extracts symptoms from user input
2. **Diagnosis Node** - Identifies disease from symptoms (placeholder - add logic here)
3. **Triage Node** - Determines facility type from disease and severity
4. **Orientation Node** - Finds nearest facility based on triage recommendation

## Node Details

### 1. Extraction Node (`extraction_node`)

**Location:** `agents/triage_agent/nodes.py`

**Purpose:** Extract symptoms (both positive and negative) from user input using NER.

**Input:**
- `user_input` (str): User's symptom description

**Output:**
- `symptoms` (List[str]): Positive symptoms extracted
- `negative_symptoms` (List[str]): Negative symptoms (negated symptoms)
- `extraction_result` (Dict): Full extraction result from NER model

**Example:**
```python
state = {
    "user_input": "I have a headache and fever, but no nausea"
}
state = extraction_node(state)
# state["symptoms"] = ["headache", "fever"]
# state["negative_symptoms"] = ["nausea"]
```

### 2. Diagnosis Node (`diagnosis_node`)

**Location:** `agents/triage_agent/nodes.py`

**Purpose:** Identify disease from symptoms. **This is a placeholder - add your diagnosis logic here.**

**Input:**
- `symptoms` (List[str]): Positive symptoms
- `negative_symptoms` (List[str]): Negative symptoms

**Output:**
- `disease` (str): Identified disease name
- `severity` (str): Severity level ("mild", "moderate", "severe")
- `confidence` (float): Confidence score (0.0-1.0)

**TODO:** Add your diagnosis model logic in this node.

**Example:**
```python
state = {
    "symptoms": ["headache", "fever"],
    "negative_symptoms": ["nausea"]
}
state = diagnosis_node(state)
# state["disease"] = "flu"
# state["severity"] = "moderate"
# state["confidence"] = 0.85
```

### 3. Triage Node (`triage_node`)

**Location:** `agents/triage_agent/nodes.py`

**Purpose:** Determine facility type from disease and severity.

**Input:**
- `disease` (str): Disease name
- `severity` (str): Severity level
- OR `user_input` (str): Format "disease,severity"
- OR `mental_health_recommendation` (str): "emergency" or "therapist" (from mental_health node)

**Output:**
- `service_type` (str): One of:
  - `HOSPITAL` - For serious/life-threatening conditions
  - `PHARMACY` - For minor conditions treatable with OTC meds
  - `CLINIC` - For moderate conditions requiring professional evaluation
  - `URGENT_CARE` - For urgent but not life-threatening conditions
  - `PSYCHIATRIST` - For mental health conditions
  - `STAY_HOME` - For mild, self-limiting conditions
- `immediate_care` (bool): Whether immediate care is needed
- `recommendation_text` (str): Human-readable recommendation

**Example:**
```python
state = {
    "disease": "flu",
    "severity": "moderate"
}
state = triage_node(state)
# state["service_type"] = "PHARMACY"
# state["immediate_care"] = False
```

### 4. Orientation Node (`orientation_node`)

**Location:** `agents/triage_agent/nodes.py`

**Purpose:** Find nearest facility based on triage recommendation.

**Input:**
- `service_type` (str): Facility type from triage node
- `user_location` (tuple): (latitude, longitude)
- OR `user_input_location` (str): Location string to geocode
- OR `mental_health_recommendation` (str): "emergency" or "therapist"

**Output:**
- `nearby_facilities` (List[Dict]): List of nearby facilities
- `selected_facility` (Dict): Nearest facility with:
  - `name` (str): Facility name
  - `distance` (float): Distance in km
  - `latitude` (float): Latitude
  - `longitude` (float): Longitude
  - `address` (str): Address if available
- `should_end` (bool): True to end workflow
- `agent_output` (str): Formatted message for user

**Example:**
```python
state = {
    "service_type": "PHARMACY",
    "user_location": (36.8065, 10.1815)  # Tunis coordinates
}
state = orientation_node(state)
# state["selected_facility"] = {
#     "name": "Pharmacy XYZ",
#     "distance": 0.5,
#     "latitude": 36.8070,
#     "longitude": 10.1820,
#     "address": "123 Main St"
# }
```

## Graph Flow

The nodes are chained in LangGraph as follows:

```
Router → Extraction → Diagnosis → Triage → Orientation → END
```

### Mental Health Integration

The mental health agent can route directly to the orientation node:

```
Mental Health Agent → Orientation Node
```

When `mental_health_recommendation` is set to:
- `"emergency"` → Routes to orientation with `service_type="PSYCHIATRIST"` and `immediate_care=True`
- `"therapist"` → Routes to orientation with `service_type="PSYCHIATRIST"` and `immediate_care=False`

## Usage

### Basic Triage Flow

```python
from agents.graph.build_graph import app

state = {
    "user_input": "I have a headache and fever",
    "user_location": (36.8065, 10.1815),  # Optional
    "messages": [],
    "agent_registry": {...}  # Injected automatically
}

result = app.invoke(state)
print(result["agent_output"])
```

### Mental Health Flow

```python
state = {
    "user_input": "I need emergency mental health help",
    "user_location": (36.8065, 10.1815),
    "messages": [],
    "agent_registry": {...}
}

# Router will route to mental_health agent
# Mental health agent sets mental_health_recommendation="emergency"
# Then routes to orientation node
result = app.invoke(state)
```

## State Fields

The following fields are added to `AgentState` for the triage workflow:

- `symptoms` (List[str]): Positive symptoms
- `negative_symptoms` (List[str]): Negative symptoms
- `extraction_result` (Dict): Full extraction result
- `disease` (str): Identified disease
- `severity` (str): Severity level
- `confidence` (float): Confidence score
- `service_type` (str): Facility type
- `immediate_care` (bool): Immediate care flag
- `recommendation_text` (str): Recommendation text
- `nearby_facilities` (List[Dict]): Nearby facilities list
- `selected_facility` (Dict): Selected facility
- `mental_health_recommendation` (str): Mental health recommendation
- `user_location` (tuple): User coordinates
- `user_input_location` (str): User location string

## Next Steps

1. **Add Diagnosis Logic:** Implement your diagnosis model in `diagnosis_node()` in `agents/triage_agent/nodes.py`
2. **Test the Flow:** Test with various symptom inputs
3. **Customize Output:** Adjust the `agent_output` formatting in each node as needed

## Files

- `agents/triage_agent/nodes.py` - Node implementations
- `agents/triage_agent/workflow.py` - Complete workflow function (optional, for backward compatibility)
- `agents/graph/build_graph.py` - LangGraph configuration
- `agents/state.py` - State definition

