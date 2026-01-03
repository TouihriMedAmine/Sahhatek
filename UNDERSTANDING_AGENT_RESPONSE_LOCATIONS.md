# Where to Find Understanding Agent Response

## Overview
The Understanding Agent (also called "router") is the first agent that processes user messages. It determines intent and routes to specialized agents.

## Response Locations

### 1. **In the Chat Interface** (User-Facing)
**Location**: Chat messages displayed to the user

**When it appears**:
- When `current_agent == "router"` in the LangGraph result
- The response is shown as an assistant message in the chat

**Code Path**:
```
agents/views.py (line ~535)
  → result.get("agent_output")
  → Displayed via appendMessage() in chat.html
```

**Example**: When user sends "Hello", the understanding agent responds with a greeting.

---

### 2. **In Response Metadata** (Backend)
**Location**: `result["metadata"]["understanding_agent"]["router_response"]`

**Code**: `agents/understanding_agent/agent.py` (line ~842)

**Contains**:
```python
{
    "understanding_agent": {
        "original_input": user_message.text,
        "detected_language": user_message.language,
        "intent": decision.intent.value,
        "confidence": decision.confidence,
        "needs_clarification": decision.needs_clarification,
        "router_response": decision.response,  # ← HERE
        "routing_to": decision.route_to
    }
}
```

---

### 3. **In Database (Message Metadata)**
**Location**: `Message.metadata` field in database

**How to access**:
```python
from agents.models import Message

message = Message.objects.get(id=message_id)
understanding_response = message.metadata.get("understanding_agent", {}).get("router_response")
```

---

### 4. **In Server Logs**
**Location**: Console/Django logs

**What to look for**:
- `"🔀 Router requested {next_agent}"`
- `"✅ LangGraph completed. Agent: router"`
- `"agent_output": "..."`

**Code**: `agents/views.py` (line ~548)

---

### 5. **In LangGraph State**
**Location**: `result["agent_output"]` after graph execution

**Code**: `agents/views.py` (line ~535)

**Example**:
```python
result = app.invoke(langgraph_state)
bot_content = result.get("agent_output")  # Understanding agent response here
current_agent = result.get("current_agent")  # Will be "router" if understanding agent responded
```

---

## When Understanding Agent Responds

The understanding agent responds when:

1. **No specialized agent is active** - User starts a new conversation
2. **Clarification needed** - User input is unclear
3. **Out of scope** - Request doesn't match any specialized agent
4. **Greeting** - User sends greeting or empty message

---

## How to Access Programmatically

### From Views:
```python
# In agents/views.py
result = app.invoke(langgraph_state)
understanding_response = result.get("agent_output")  # Direct response
understanding_metadata = result.get("metadata", {}).get("understanding_agent", {})
router_response = understanding_metadata.get("router_response")  # Same as above
```

### From Message Model:
```python
from agents.models import Message

message = Message.objects.filter(conversation_id=conv_id, role='assistant').first()
if message:
    understanding_data = message.metadata.get("understanding_agent", {})
    router_response = understanding_data.get("router_response")
```

### From Frontend (JavaScript):
```javascript
// In chat.html
// The response is already displayed, but you can access it from message metadata:
const messageDiv = document.querySelector('[data-message-id="..."]');
const metadata = JSON.parse(messageDiv.dataset.metadata || '{}');
const understandingResponse = metadata.understanding_agent?.router_response;
```

---

## Response Examples

### Greeting Response:
```
"Hello! I'm Sahatek, your medical assistant. I can help with:
• Medical questions (medical_qa)
• Symptom assessment (triage)
• Mental health support (mental_health)
• Medical rumor verification (rumor)
• Wound analysis (wound_analyzer)

How can I help you today?"
```

### Clarification Response:
```
"I want to make sure I understand correctly. Could you please provide more details about your medical concern?"
```

### Routing Response:
```
"I understand. Let me connect you to the right specialist..."
```

---

## Key Files

1. **Understanding Agent Logic**: `agents/understanding_agent/agent.py`
   - `router_agent()` method (line ~661)
   - Returns `agent_output` with response

2. **Graph Integration**: `agents/graph/build_graph.py`
   - Router node added at line ~151
   - Entry point for conversations

3. **View Handler**: `agents/views.py`
   - Line ~535: Extracts `agent_output`
   - Line ~548: Logs completion

4. **Frontend Display**: `templates/chat.html`
   - Line ~2203: `appendMessage()` displays response
   - Line ~2224: Renders message content

---

## Debugging Tips

1. **Check if router responded**:
   ```python
   if result.get("current_agent") == "router":
       print(f"Understanding agent response: {result.get('agent_output')}")
   ```

2. **Check metadata**:
   ```python
   understanding_meta = result.get("metadata", {}).get("understanding_agent", {})
   print(f"Router response: {understanding_meta.get('router_response')}")
   print(f"Routing to: {understanding_meta.get('routing_to')}")
   ```

3. **Check logs**:
   - Look for "🔀 Router requested" messages
   - Check for "agent_output" in JSON logs

---

## Summary

**Primary Location**: `result["agent_output"]` in views.py (line ~535)

**Metadata Location**: `result["metadata"]["understanding_agent"]["router_response"]` (line ~842 in agent.py)

**Display Location**: Chat interface via `appendMessage()` in chat.html (line ~2203)

**Database Location**: `Message.metadata["understanding_agent"]["router_response"]`

