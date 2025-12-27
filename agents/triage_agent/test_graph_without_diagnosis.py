# agents/triage_agent/test_graph_without_diagnosis.py
"""
Test the LangGraph workflow without diagnosis node.
This creates a modified graph that skips diagnosis and uses manual disease/severity.
"""

import sys
import os

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.triage_agent.nodes import (
    extraction_node,
    triage_node,
    orientation_node
)

# CONFIG: Manual disease/severity for testing (since we skip diagnosis)
MANUAL_DISEASE = "flu"
MANUAL_SEVERITY = "moderate"


def mock_diagnosis_node(state: dict) -> dict:
    """
    Mock diagnosis node that just sets manual disease/severity.
    Replace this with your actual diagnosis logic later.
    """
    # Use manual values for testing
    state["disease"] = MANUAL_DISEASE
    state["severity"] = MANUAL_SEVERITY
    state["confidence"] = 0.8
    
    print(f"🔧 Mock Diagnosis: disease='{MANUAL_DISEASE}', severity='{MANUAL_SEVERITY}'")
    return state


# Build test graph
print("🔧 Building test graph (without real diagnosis)...")
graph = StateGraph(AgentState)

# Add nodes
graph.add_node("extraction", extraction_node)
graph.add_node("diagnosis", mock_diagnosis_node)  # Mock diagnosis
graph.add_node("triage", triage_node)
graph.add_node("orientation", orientation_node)

# Chain nodes
graph.add_edge("extraction", "diagnosis")
graph.add_edge("diagnosis", "triage")
graph.add_edge("triage", "orientation")

# Orientation ends
def orientation_router(state):
    return END

graph.add_conditional_edges("orientation", orientation_router, {END: END})

# Set entry point
graph.set_entry_point("extraction")

# Compile
app = graph.compile()
print("✅ Test graph compiled successfully!\n")


if __name__ == "__main__":
    # Test configuration
    TEST_INPUT = "I have a headache, fever, and I feel tired"
    TEST_LOCATION = (36.8065, 10.1815)  # Tunis - change to your location
    
    print("="*60)
    print("TESTING TRIAGE WORKFLOW (WITHOUT REAL DIAGNOSIS)")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  User input: {TEST_INPUT}")
    print(f"  Manual disease: {MANUAL_DISEASE}")
    print(f"  Manual severity: {MANUAL_SEVERITY}")
    print(f"  Location: {TEST_LOCATION}")
    print("\n" + "="*60 + "\n")
    
    # Create test state
    test_state = {
        "user_input": TEST_INPUT,
        "user_location": TEST_LOCATION,
        "symptoms": [],
        "negative_symptoms": [],
        "messages": [],
        "agent_registry": {},
        "metadata": {}
    }
    
    try:
        # Run the graph
        print("🚀 Running workflow...\n")
        result = app.invoke(test_state)
        
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        print(f"\n✅ Extracted symptoms: {result.get('symptoms', [])}")
        print(f"✅ Disease: {result.get('disease')}")
        print(f"✅ Severity: {result.get('severity')}")
        print(f"✅ Service type: {result.get('service_type')}")
        print(f"✅ Immediate care: {result.get('immediate_care')}")
        
        selected = result.get('selected_facility')
        if selected:
            print(f"\n📍 Nearest facility:")
            print(f"   Name: {selected.get('name')}")
            print(f"   Distance: {selected.get('distance')} km")
            print(f"   Address: {selected.get('address', 'N/A')}")
        
        print(f"\n💬 Final output:\n{result.get('agent_output', '')}")
        
        print("\n" + "="*60)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

