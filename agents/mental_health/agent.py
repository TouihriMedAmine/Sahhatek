# agents/mental_agent/agent.py
from typing import Dict, Any, List
from agents.state import AgentState
from agents.mental_health.service import (
    detect_urgency,
    build_alert_banner,
    retrieve_relevant_techniques,
    format_rag_context,
    analyze_situation,
    generate_plan,
    continue_conversation,
)
# 🎯 LangSmith Integration
from agents.langsmith_decorators import (
    trace_agent_node, add_metadata_to_state
)

@trace_agent_node("mental_health_agent", "🧠_MentalHealth_Processing")
def mental_health_agent(state: AgentState) -> AgentState:
    """
    LangGraph node:
    - Reads user_input + messages
    - Detects urgency (crisis / emergency / mental_health_urgent)
    - Uses Chroma RAG (unless TEST_MODE)
    - Produces agent_output
    - Updates messages/current_agent/next_agent
    """
    user_input: str = (state.get("user_input") or "").strip()
    messages: List[Dict[str, str]] = state.get("messages") or []
    metadata: Dict[str, Any] = state.get("metadata") or {}

    state["current_agent"] = "mental_health"
    state["next_agent"] = None
    
    # 🧹 CLEAN UP TRIAGE DATA - Reset diagnosis state when switching to mental health
    state["pending_questions"] = []
    state["should_end"] = False
    state["diagnosis_session_id"] = None
    state["symptoms_found"] = []
    state["diagnoses"] = []
    state["healthcare_recommendation"] = None

    # 1) Urgency detection
    urgency = detect_urgency(user_input)
    alert = build_alert_banner(urgency) if urgency else ""
    metadata.setdefault("safety", {})
    metadata["safety"]["urgency_level"] = urgency
    metadata["safety"]["urgency_detected"] = bool(urgency)

    # 2) RAG context
    docs = retrieve_relevant_techniques(user_input, k=4)
    rag_context = format_rag_context(docs)
    metadata["rag"] = {"k": 4, "hits": len(docs), "collection": "wellbeing_kb"}

    # 3) Decide first turn vs continued
    has_assistant_history = any(m.get("role") == "assistant" for m in messages)
    if not has_assistant_history:
        analysis = analyze_situation(user_input, rag_context, history=messages)
        response = generate_plan(user_input, rag_context, analysis, history=messages)
        metadata["mental"] = {"mode": "analysis+plan"}
    else:
        response = continue_conversation(user_input, history=messages, rag_context=rag_context)
        metadata["mental"] = {"mode": "chat"}

    # 4) Prepend alert if needed
    if alert:
        response = f"{alert}\n---\n{response}"

    # 5) Update state avec métadonnées LangSmith
    state = add_metadata_to_state(state, "mental_health_agent", "processing", {
        "urgency_level": urgency,
        "rag_docs_retrieved": len(docs),
        "conversation_mode": metadata.get("mental", {}).get("mode"),
        "safety_alert_triggered": bool(alert)
    })
    
    # 6) Set output and metadata
    state["agent_output"] = response
    state["metadata"] = metadata
    
    return state
