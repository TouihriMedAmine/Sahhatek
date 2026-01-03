# agents/graph/build_graph.py - FINAL VERSION with Wound Analyzer
import sys
import os
import logging
from typing import Dict, Any
from datetime import datetime

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
        elif any(word in user_input for word in ["wound", "cut", "bleeding", "burn", "rash", "skin"]):
            state["intent"] = "wound_analyzer"  # Added wound keywords
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
    def medical_qa_agent(state: Dict[str, Any]) -> Dict[str, Any]:
        state["agent_output"] = "🏥 MEDICAL Q/A AGENT (Fallback): " + state.get("user_input", "")
        state["current_agent"] = "medical_qa"
        return state

# Triage workflow - New node-based workflow
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
    def mental_health_agent(state: Dict[str, Any]) -> Dict[str, Any]:
        state["agent_output"] = "💙 MENTAL HEALTH AGENT: " + state.get("user_input", "")
        state["current_agent"] = "mental_health"
        return state

# Rumor Verification Agent
try:
    from agents.rumor.agent import rumor_verification_agent
    print("✅ Imported Rumor Verification Agent")
    rumor_agent = rumor_verification_agent
except ImportError as e:
    print(f"⚠️ Rumor Verification Agent not found: {e}")
    def rumor_agent(state: Dict[str, Any]) -> Dict[str, Any]:
        state["agent_output"] = "🔍 RUMOR DETECTION AGENT: " + state.get("user_input", "")
        state["current_agent"] = "rumor"
        return state

# Wound Analyzer Agent (NEW)
try:
    from agents.wound_analyzer.agent import wound_analyzer_agent
    print("✅ Imported Wound Analyzer Agent")
except ImportError as e:
    print(f"⚠️ Wound Analyzer Agent not found: {e}")
    # Fallback wound analyzer agent
    def wound_analyzer_agent(state: Dict[str, Any]) -> Dict[str, Any]:
        user_input = state.get("user_input", "").lower()
        
        # Extract wound info from metadata
        metadata = state.get("metadata", {})
        has_image = metadata.get("has_wound_image", False)
        wound_type = metadata.get("wound_type", "")
        
        # Check for emergency wound keywords
        emergency_keywords = ["bleeding heavily", "severe pain", "deep cut", "large burn", "broken bone", 
                             "animal bite", "unconscious", "difficulty breathing"]
        
        is_emergency = any(keyword in user_input for keyword in emergency_keywords)
        
        if is_emergency:
            state["wound_analysis"] = {
                "severity": "high",
                "urgency": "immediate",
                "needs_urgent_referral": True,
                "recommendation": "Seek emergency medical attention immediately"
            }
        else:
            state["wound_analysis"] = {
                "severity": "low_to_medium",
                "urgency": "non_urgent",
                "needs_urgent_referral": False,
                "recommendation": "Monitor the wound and seek medical advice if symptoms worsen"
            }
        
        state["agent_output"] = "🩹 WOUND ANALYZER AGENT: I've analyzed your wound concern. " + (
            "This appears to be an emergency situation. Seek immediate medical attention." if is_emergency else
            "Based on your description, this appears manageable with proper wound care."
        )
        state["current_agent"] = "wound_analyzer"
        return state

print("✅ All agents loaded (including Wound Analyzer)")

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

# Wound Analyzer Agent (NEW)
graph.add_node("wound_analyzer", wound_analyzer_agent)

# Entry point - CHANGED: Now we have a special entry decision
graph.set_entry_point("entry_decision")

# ------------------ ENTRY DECISION (IMPROVED VERSION) ------------------
def entry_decision(state: AgentState) -> str:
    """
    Decide where to enter the graph.
    IMPORTANT: This handles FORCED AGENT routing for card clicks.
    """
    print("=" * 60)
    print("🔍 ENTRY DECISION - RECEIVED STATE:")
    
    # Get metadata
    metadata = state.get("metadata", {})
    conversation_metadata = metadata.get("conversation_metadata", {})
    message_type = metadata.get("message_type", "regular")
    direct_agent_request = metadata.get("direct_agent_request", False)
    
    print(f"   Message type: {message_type}")
    print(f"   Direct agent request: {direct_agent_request}")
    print(f"   Conversation metadata: {conversation_metadata}")
    
    # CRITICAL: Check if this conversation has a preferred agent from metadata
    # This is set when a conversation is created via direct agent message
    if conversation_metadata and "agent" in conversation_metadata:
        preferred_agent = conversation_metadata["agent"]
        print(f"🎯 PREFERRED AGENT DETECTED in conversation metadata: {preferred_agent}")
        
        # Map card agent names to graph nodes (UPDATED with wound analyzer)
        agent_mapping = {
            # Card agent names → Graph node names
            "mental-health": "mental_health",
            "symptoms-checker": "extraction",  # Start at extraction for triage workflow
            "general-info": "medical_qa",
            "rumor-check": "rumor",
            "orientation": "orientation",
            "wound-analyzer": "wound_analyzer",  # NEW: Wound analyzer mapping
            
            # Also support intent names
            "mental_health": "mental_health",
            "medical_qa": "medical_qa",
            "triage": "extraction",
            "rumor": "rumor",
            "wound_analyzer": "wound_analyzer",  # NEW
            "general": "router"
        }
        
        mapped_agent = agent_mapping.get(preferred_agent)
        
        if mapped_agent:
            print(f"📍 Mapping {preferred_agent} → {mapped_agent}")
            
            # Track in metadata for debugging
            if "metadata" not in state:
                state["metadata"] = {}
            state["metadata"]["preferred_routing"] = {
                "original_agent": preferred_agent,
                "mapped_to": mapped_agent,
                "timestamp": datetime.now().isoformat(),
                "reason": "conversation_metadata"
            }
            
            # Special handling for symptoms-checker/triage
            if preferred_agent in ["symptoms-checker", "triage"]:
                if "metadata" not in state:
                    state["metadata"] = {}
                state["metadata"]["is_triage_conversation"] = True
                print(f"🔀 Setting is_triage_conversation flag for {preferred_agent}")
            
            # Special handling for wound analyzer
            if preferred_agent == "wound-analyzer":
                if "metadata" not in state:
                    state["metadata"] = {}
                state["metadata"]["is_wound_analysis"] = True
                print(f"🔀 Setting is_wound_analysis flag")
            
            # Also set current_agent to help with tracking
            state["current_agent"] = mapped_agent
            
            return mapped_agent
    
    # Check for forced agent routing (from direct_agent_message endpoint)
    forced_from_meta = metadata.get("requested_agent")
    forced_from_root = state.get("forced_agent")
    
    if forced_from_meta or forced_from_root:
        forced_agent = forced_from_meta or forced_from_root
        print(f"🎯 FORCED AGENT DETECTED: {forced_agent}")
        
        agent_mapping = {
            "mental-health": "mental_health",
            "symptoms-checker": "extraction",
            "general-info": "medical_qa",
            "rumor-check": "rumor",
            "orientation": "orientation",
            "wound-analyzer": "wound_analyzer",  # NEW
            "mental_health": "mental_health",
            "medical_qa": "medical_qa",
            "triage": "extraction",
            "rumor": "rumor",
            "wound_analyzer": "wound_analyzer"  # NEW
        }
        
        mapped_agent = agent_mapping.get(forced_agent)
        
        if mapped_agent:
            print(f"📍 Mapping forced {forced_agent} → {mapped_agent}")
            
            # Track in metadata
            if "metadata" not in state:
                state["metadata"] = {}
            state["metadata"]["forced_routing"] = {
                "original_agent": forced_agent,
                "mapped_to": mapped_agent,
                "timestamp": datetime.now().isoformat(),
                "was_forced": True
            }
            
            # Clear forced_agent to prevent infinite loops
            if "forced_agent" in state:
                state["forced_agent"] = None
            
            # Set current_agent
            state["current_agent"] = mapped_agent
            
            return mapped_agent
    
    # Default: start with router
    print("🔄 No preferred or forced routing detected, starting with router")
    state["current_agent"] = "router"
    return "router"

# Add entry decision node
graph.add_node("entry_decision", lambda state: state)  # Just passes state through

# Add conditional edges from entry decision (UPDATED with wound_analyzer)
graph.add_conditional_edges(
    "entry_decision",
    entry_decision,
    {
        "router": "router",
        "medical_qa": "medical_qa",
        "extraction": "extraction",
        "diagnosis": "diagnosis",
        "triage": "triage",
        "mental_health": "mental_health",
        "rumor": "rumor",
        "orientation": "orientation",
        "wound_analyzer": "wound_analyzer",  # NEW
        "triage_workflow": "triage_workflow",
        END: END
    }
)

# ------------------ CONDITIONAL ROUTING FROM ROUTER ------------------
def gatekeeper_routing_decision(state: AgentState) -> str:
    """
    Decide which agent to route to next FROM ROUTER.
    This is only used when we start with the router (general conversations).
    """
    logger = logging.getLogger(__name__)
    
    # Get state variables
    pending_questions = state.get("pending_questions", [])
    user_input = state.get("user_input", "").strip()
    diagnosis_session_id = state.get("diagnosis_session_id")
    next_agent = state.get("next_agent")
    should_end = state.get("should_end", False)
    intent = state.get("intent")
    
    # Get metadata
    metadata = state.get("metadata", {})
    conversation_metadata = metadata.get("conversation_metadata", {})
    
    print("=" * 60)
    print("🔀 GATEKEEPER ROUTING DECISION:")
    print(f"   User input: {user_input[:50]}...")
    print(f"   Intent: {intent}")
    print(f"   Next agent: {next_agent}")
    print(f"   Conversation metadata: {conversation_metadata}")
    print(f"   Pending questions: {len(pending_questions)}")
    
    # CRITICAL: Check if this is a specialized conversation that should bypass router
    # If conversation has an agent in metadata, skip router and go directly to that agent
    if conversation_metadata and "agent" in conversation_metadata:
        preferred_agent = conversation_metadata["agent"]
        print(f"🎯 SPECIALIZED CONVERSATION DETECTED - bypassing router for: {preferred_agent}")
        
        # Map to graph node (UPDATED)
        agent_mapping = {
            "mental-health": "mental_health",
            "symptoms-checker": "extraction",
            "general-info": "medical_qa",
            "rumor-check": "rumor",
            "orientation": "orientation",
            "wound-analyzer": "wound_analyzer"  # NEW
        }
        
        mapped_agent = agent_mapping.get(preferred_agent)
        
        if mapped_agent:
            print(f"📍 Routing directly to {mapped_agent} (bypassing router)")
            
            # Update metadata
            if "metadata" not in state:
                state["metadata"] = {}
            state["metadata"]["router_bypassed"] = True
            state["metadata"]["preferred_agent_used"] = preferred_agent
            
            return mapped_agent
    
    # CRITICAL: Check next_agent from router decision FIRST (before triage check)
    # This ensures router's explicit routing (e.g., mental_health) takes priority
    if next_agent:
        print(f"🔀 Router requested {next_agent}")
        
        intent_mapping = {
            "medical_qa": "medical_qa",
            "mental_health": "mental_health",
            "rumor": "rumor",
            "triage": "extraction",
            "wound_analyzer": "wound_analyzer",  # NEW
            "orientation": "orientation"  # NEW - for direct facility requests
        }
        
        mapped_agent = intent_mapping.get(next_agent, next_agent)
        print(f"📍 Mapping {next_agent} → {mapped_agent}")
        
        # If router explicitly routes to a specialized agent (not triage), respect that
        # Only allow triage override if router itself routes to triage
        # Also allow orientation (for direct facility requests)
        if mapped_agent not in ["extraction", "diagnosis"]:
            print(f"✅ Router explicitly routed to {mapped_agent}, ignoring pending triage questions")
            return mapped_agent
    
    # Check if user is answering a triage question (only if router didn't route elsewhere)
    if pending_questions and user_input and diagnosis_session_id:
        print(f"🔀 Answering triage question - routing to diagnosis")
        return "diagnosis"
    
    # Check intent from router (UPDATED)
    if intent:
        intent_mapping = {
            "medical_qa": "medical_qa",
            "mental_health": "mental_health",
            "rumor": "rumor",
            "triage": "extraction",
            "wound_analyzer": "wound_analyzer",  # NEW
            "orientation": "orientation"  # NEW - for direct facility requests
        }
        mapped_intent = intent_mapping.get(intent)
        if mapped_intent:
            print(f"🔄 Router intent '{intent}' - routing to '{mapped_intent}'")
            return mapped_intent
    
    # ====== DEFAULT: End the graph ======
    if should_end:
        print(f"🔄 should_end=True, ending graph")
        return END
    
    print("🔄 No valid routing decision, ending graph")
    return END

graph.add_conditional_edges(
    "router",
    gatekeeper_routing_decision,
    {
        "medical_qa": "medical_qa",
        "extraction": "extraction",
        "diagnosis": "diagnosis",
        "triage": "triage",
        "mental_health": "mental_health",
        "rumor": "rumor",
        "wound_analyzer": "wound_analyzer",  # NEW
        "orientation": "orientation",
        "triage_workflow": "triage_workflow",
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
    """Route diagnosis node"""
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
        "diagnosis": "diagnosis",
        "triage": "triage",
        END: END,
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
    if state.get("mental_health_recommendation") in ["emergency", "therapist"]:
        logger.info("🔀 Mental health agent recommending orientation")
        return "orientation"
    
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

# Wound analyzer routing - can end or route to orientation if urgent (NEW)
def wound_analyzer_router(state: AgentState):
    """Route after wound analysis"""
    # Check if wound analysis indicates urgent referral
    wound_analysis = state.get("wound_analysis", {})
    
    if wound_analysis.get("needs_urgent_referral"):
        print("🔀 Wound analysis recommending urgent orientation")
        return "orientation"
    
    # Check metadata for wound analysis
    metadata = state.get("metadata", {})
    if metadata.get("wound_analysis", {}).get("needs_urgent_referral"):
        print("🔀 Wound analysis (metadata) recommending urgent orientation")
        return "orientation"
    
    print("✅ Wound analysis complete - ending conversation")
    return END

graph.add_conditional_edges(
    "wound_analyzer",
    wound_analyzer_router,
    {
        "orientation": "orientation",
        END: END,
    }
)

# Add conditional edges for delegation (UPDATED)
for agent in ["medical_qa", "rumor", "orientation"]:
    graph.add_conditional_edges(
        agent,
        agent_router,
        {
            "medical_qa": "medical_qa",
            "triage": "extraction",
            "mental_health": "mental_health",
            "rumor": "rumor",
            "wound_analyzer": "wound_analyzer",  # NEW
            "orientation": "orientation",
            END: END,
        }
    )

# ------------------ COMPILE GRAPH ------------------
app = graph.compile()
print("🎉 LangGraph with Direct Agent Entry and Wound Analyzer compiled successfully!")

# ------------------ TEST GRAPH ------------------
if __name__ == "__main__":
    print("\n🧪 Testing the graph...")
    
    # Test 1: Direct agent conversation (wound analyzer)
    print("\n🧪 Testing wound analyzer conversation...")
    test_state = {
        "user_input": "I have a deep cut on my arm",
        "intent": None,
        "messages": [],
        "current_agent": None,
        "next_agent": None,
        "agent_output": None,
        "metadata": {
            "message_type": "direct_agent",
            "conversation_metadata": {
                "agent": "wound-analyzer"
            },
            "has_wound_image": False,
            "wound_type": "cut"
        }
    }

    try:
        result = app.invoke(test_state)
        print(f"✅ Test passed!")
        print(f"   Conversation agent: wound-analyzer")
        print(f"   Current agent: {result.get('current_agent')}")
        print(f"   Router bypassed: {result.get('metadata', {}).get('router_bypassed', False)}")
        print(f"   Output: {result.get('agent_output', '')[:100]}...")
        
        # Check wound analysis data
        if "wound_analysis" in result:
            print(f"   Wound analysis: {result['wound_analysis']}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    # Test 2: Regular message with wound keywords
    print("\n🧪 Testing regular message with wound keywords...")
    test_state2 = {
        "user_input": "I have a burn on my hand from cooking",
        "intent": None,
        "messages": [],
        "current_agent": None,
        "next_agent": None,
        "agent_output": None,
        "metadata": {
            "message_type": "regular"
        }
    }
    
    try:
        result2 = app.invoke(test_state2)
        print(f"✅ Test 2 passed!")
        print(f"   Intent detected: {result2.get('intent')}")
        print(f"   Current agent: {result2.get('current_agent')}")
        print(f"   Output: {result2.get('agent_output', '')[:100]}...")
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")