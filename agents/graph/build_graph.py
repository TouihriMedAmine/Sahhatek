# agents/graph/build_graph.py
import sys
import os
import logging
from typing import Dict, Any

# Setup logging
logger = logging.getLogger(__name__)

# Fix Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.graph.registry import AGENT_REGISTRY

print("🔧 Loading agents for LangGraph...")

# ------------------ IMPORT AGENTS ------------------
# Understanding Agent
try:
    from agents.understanding_agent.agent import router_agent
    print("✅ Imported Understanding Agent (Clean Version)")
except ImportError as e:
    print(f"⚠️ Understanding Agent not found: {e}")
    print("⚠️ Using fallback router_agent")
    # Fallback router agent
    def router_agent(state: Dict[str, Any]) -> Dict[str, Any]:
        user_input = state.get("user_input", "").lower()
        if any(word in user_input for word in ["urgent", "emergency", "severe"]):
            state["intent"] = "triage"
        elif any(word in user_input for word in ["depressed", "anxious", "mental"]):
            state["intent"] = "mental_health"
        elif any(word in user_input for word in ["true", "rumor", "myth"]):
            state["intent"] = "rumor"
        elif any(word in user_input for word in ["symptom", "pain", "fever", "cough"]):
            state["intent"] = "medical_qa"
        else:
            state["intent"] = "general"
        state["current_agent"] = "router"
        return state

# Medical Q/A Agent
try:
    from agents.medical_agent.agent import medical_qa_agent
    print("✅ Imported Medical Q/A Agent")
except ImportError as e:
    print(f"❌ Failed to import Medical Q/A Agent: {e}")
    raise

# Triage Agent - New node-based workflow
try:
    from agents.triage_agent.workflow import triage_workflow
    from agents.triage_agent.nodes import (
        extraction_node,
        diagnosis_node,
        triage_node,
        orientation_node
    )
    print("✅ Imported Triage Workflow (Node-based)")
except ImportError as e:
    print(f"❌ Failed to import Triage Workflow: {e}")
    # Fallback to old triage agent
    try:
        from agents.triage_agent.agent import triage_agent as triage_workflow
        print("⚠️ Using fallback triage agent")
    except ImportError as e2:
        print(f"❌ Failed to import fallback Triage Agent: {e2}")
        raise

# Mental Health Agent
try:
    from agents.mental_health.agent import mental_health_agent
    print("✅ Imported Mental Health Agent")
except ImportError as e:
    print(f"⚠️ Mental Health Agent not found: {e}")
    # Fallback mental health agent
    def mental_health_agent(state: Dict[str, Any]) -> Dict[str, Any]:
        """Mental health agent - can route to orientation with 'emergency' or 'therapist'"""
        user_input = state.get("user_input", "").lower()
        
        # Check if it's an emergency or therapist recommendation
        if "emergency" in user_input or "urgent" in user_input:
            state["mental_health_recommendation"] = "emergency"
            state["next_agent"] = "orientation"
        elif "therapist" in user_input or "therapy" in user_input:
            state["mental_health_recommendation"] = "therapist"
            state["next_agent"] = "orientation"
        else:
            state["agent_output"] = "💙 MENTAL HEALTH AGENT: " + state.get("user_input", "")
        
        state["current_agent"] = "mental_health"
        return state

# Rumor Verification Agent
try:
    from agents.rumor.agent import rumor_verification_agent
    print("✅ Imported Rumor Verification Agent")
    # Alias for consistency
    rumor_agent = rumor_verification_agent
except ImportError as e:
    print(f"⚠️ Rumor Verification Agent not found: {e}")
    # Fallback rumor agent
    def rumor_agent(state: Dict[str, Any]) -> Dict[str, Any]:
        state["agent_output"] = "🔍 RUMOR DETECTION AGENT: " + state.get("user_input", "")
        state["current_agent"] = "rumor"
        return state

print("✅ All agents loaded")

# ------------------ BUILD THE GRAPH ------------------
graph = StateGraph(AgentState)

# Add nodes with clear names for LangSmith tracing
graph.add_node("router", router_agent)

# Medical Q&A Agent
graph.add_node("medical_qa", medical_qa_agent)

# Triage workflow nodes
graph.add_node("extraction", extraction_node)
graph.add_node("diagnosis", diagnosis_node)
graph.add_node("triage", triage_node)
graph.add_node("orientation", orientation_node)

# For backward compatibility, also add the workflow as a single node
graph.add_node("triage_workflow", triage_workflow)

# Mental Health Agent
graph.add_node("mental_health", mental_health_agent)

# Rumor Verification Agent
graph.add_node("rumor", rumor_agent)

# Entry point
graph.set_entry_point("router")

# ------------------ CONDITIONAL ROUTING ------------------
def gatekeeper_routing_decision(state: AgentState) -> str:
    """
    Decide which agent to route to next.
    IMPORTANT: Prioritize explicit next_agent from router over pending_questions
    """
    logger = logging.getLogger(__name__)
    
    # Get state variables
    pending_questions = state.get("pending_questions", [])
    user_input = state.get("user_input", "").strip()
    diagnosis_session_id = state.get("diagnosis_session_id")
    next_agent = state.get("next_agent")
    should_end = state.get("should_end", False)
    
    logger.info(f"🔀 Gatekeeper - next_agent: {next_agent}, pending_questions: {len(pending_questions)}")
    
    # CRITICAL: Check next_agent FIRST
    # If router says go to mental_health/medical_qa/rumor, honor it (even if pending questions)
    if next_agent in ["mental_health", "medical_qa", "rumor"]:
        logger.info(f"🔀 PRIORITY: Router requested {next_agent} - honoring explicit routing")
        return next_agent
    
    # Check for direct facility request - route to orientation
    if next_agent == "orientation" and state.get("service_type"):
        logger.info(f"📍 Direct facility request - routing to orientation")
        return "orientation"
    
    # NOW check if user is answering a triage question
    # Only if next_agent is None or "triage" AND we have pending questions
    if pending_questions and user_input and diagnosis_session_id and (next_agent is None or next_agent == "triage"):
        # User is answering a triage question - route directly to diagnosis
        logger.info(f"🔀 Pending questions detected ({len(pending_questions)}) AND no explicit routing - routing to diagnosis")
        return "diagnosis"
    
    if next_agent == "triage":
        # Route to triage workflow start (extraction)
        logger.info("🔄 Routing 'triage' to 'extraction' (triage workflow start)")
        return "extraction"
    
    # End if should_end is True (for greeting or out of scope)
    if should_end:
        logger.info(f"🔄 should_end=True, ending graph")
        return END
    
    logger.info("🔄 No valid routing decision, ending graph")
    return END

graph.add_conditional_edges(
    "router",
    gatekeeper_routing_decision,
    {
        "medical_qa": "medical_qa",
        "extraction": "extraction",  # Triage workflow starts here
        "diagnosis": "diagnosis",    # Route directly to diagnosis for Q&A answers
        "triage": "extraction",      # Also handle "triage" routing
        "mental_health": "mental_health",
        "rumor": "rumor",
        "orientation": "orientation",  # Direct facility requests
        END: END
    }
)

# ------------------ AGENT-TO-AGENT DELEGATION ------------------
def agent_router(state: AgentState):
    """
    Safely routes to allowed next agents based on agent_registry.
    """
    # Inject agent_registry if missing
    if "agent_registry" not in state:
        state["agent_registry"] = AGENT_REGISTRY

    next_agent = state.get("next_agent")
    if not next_agent:
        return END

    current_agent = state.get("current_agent")
    allowed = state.get("agent_registry", {}).get(current_agent, {}).get("can_delegate_to", [])

    if next_agent in allowed:
        return next_agent
    return END

# Triage workflow: chain extraction -> diagnosis -> triage -> orientation
graph.add_edge("extraction", "diagnosis")

# Diagnosis can loop back to itself if pending questions, or proceed to triage
def diagnosis_router(state: AgentState):
    """Route diagnosis node - END if question asked (wait for user), loop back if answer received, else proceed to triage"""
    import logging
    logger = logging.getLogger(__name__)
    
    pending_questions = state.get("pending_questions", [])
    user_input = state.get("user_input", "").strip()
    should_end = state.get("should_end", False)
    
    # If should_end is True (question was just asked), END to wait for user
    if should_end:
        logger.info("❓ Question asked - ending graph to wait for user response")
        return END
    
    # If there are pending questions AND user provided input (answer), loop back to process answer
    # But only if should_end is False (meaning we're processing an answer, not asking a question)
    if pending_questions and user_input and not should_end:
        logger.info("❓ Processing answer to pending question - looping back to diagnosis")
        return "diagnosis"
    
    # If diagnosis is complete, proceed to triage
    if state.get("diagnosis_complete"):
        logger.info("✅ Diagnosis complete - proceeding to triage")
        return "triage"
    
    # Default: proceed to triage (will handle if no diagnosis)
    return "triage"

graph.add_conditional_edges(
    "diagnosis",
    diagnosis_router,
    {
        "diagnosis": "diagnosis",  # Loop back to process answer
        "triage": "triage",        # Proceed to triage when complete
        END: END,                  # End when question asked (wait for user)
    }
)

graph.add_edge("triage", "orientation")

# Orientation can end or route elsewhere
def orientation_router(state: AgentState):
    """Route after orientation"""
    if state.get("should_end"):
        return END
    return END

graph.add_conditional_edges(
    "orientation",
    orientation_router,
    {END: END}
)

# Mental health can route to orientation or end
def mental_health_router(state: AgentState):
    """Route mental health to orientation if recommendation provided, otherwise end conversation"""
    # If mental health recommends orientation (emergency/therapist), route there
    if state.get("mental_health_recommendation") in ["emergency", "therapist"]:
        logger.info("🔀 Mental health agent recommending orientation")
        return "orientation"
    
    # Otherwise, end the conversation (mental health is complete)
    logger.info("✅ Mental health support complete - ending conversation")
    return END

graph.add_conditional_edges(
    "mental_health",
    mental_health_router,
    {
        "orientation": "orientation",
        END: END,
    }
)

# Add conditional edges for delegation
for agent in ["medical_qa", "rumor"]:
    # Standard agent routing for other agents
    graph.add_conditional_edges(
        agent,
        agent_router,
        {
            "medical_qa": "medical_qa",
            "triage": "extraction",  # Route to triage workflow start
            "mental_health": "mental_health",
            "rumor": "rumor",
            END: END,
        }
    )

# ------------------ COMPILE GRAPH ------------------
app = graph.compile()
print("🎉 LangGraph with Medical Gatekeeper compiled successfully!")

# ------------------ TEST GRAPH ------------------
if __name__ == "__main__":
    print("\n🧪 Testing the graph...")
    test_state = {
        "user_input": "What is an asthma attack?",
        "intent": None,
        "messages": [],
        "current_agent": None,
        "next_agent": None,
        "agent_output": None,
        "metadata": {}
        # agent_registry will be injected automatically
    }

    try:
        result = app.invoke(test_state)
        print(f"✅ Test passed!")
        print(f"   Intent: {result.get('intent')}")
        print(f"   Agent: {result.get('current_agent')}")
        print(f"   Output: {result.get('agent_output', '')[:100]}...")
    except Exception as e:
        print(f"❌ Test failed: {e}")
