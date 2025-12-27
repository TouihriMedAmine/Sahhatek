# agents/triage_agent/test_nodes.py
"""
Test script for triage nodes without diagnosis node.
Allows testing extraction, triage, and orientation nodes individually.
"""

import sys
import os

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agents.triage_agent.nodes import (
    extraction_node,
    diagnosis_node,
    triage_node,
    orientation_node
)

# CONFIG: Adjust these values for testing
TEST_USER_INPUT = "I have a headache, fever, and I feel tired"
TEST_DISEASE = "flu"  # Manually set disease for testing
TEST_SEVERITY = "moderate"  # Manually set severity for testing
TEST_LOCATION = (36.8065, 10.1815)  # Tunis coordinates - change to your location
# OR use a location string:
# TEST_LOCATION_STRING = "Tunis, Tunisia"


def test_extraction():
    """Test extraction node"""
    print("\n" + "="*60)
    print("TEST 1: EXTRACTION NODE")
    print("="*60)
    
    state = {
        "user_input": TEST_USER_INPUT,
        "symptoms": [],
        "negative_symptoms": []
    }
    
    print(f"Input: {state['user_input']}")
    print("\nRunning extraction node...")
    
    result = extraction_node(state)
    
    print(f"\n✅ Results:")
    print(f"  Positive symptoms: {result.get('symptoms', [])}")
    print(f"  Negative symptoms: {result.get('negative_symptoms', [])}")
    print(f"  Agent output: {result.get('agent_output', '')}")
    
    return result


def test_triage(disease=None, severity=None):
    """Test triage node with manual disease/severity"""
    print("\n" + "="*60)
    print("TEST 2: TRIAGE NODE")
    print("="*60)
    
    state = {
        "disease": disease or TEST_DISEASE,
        "severity": severity or TEST_SEVERITY,
        "user_input": f"{disease or TEST_DISEASE},{severity or TEST_SEVERITY}"
    }
    
    print(f"Input: disease='{state['disease']}', severity='{state['severity']}'")
    print("\nRunning triage node...")
    
    result = triage_node(state)
    
    print(f"\n✅ Results:")
    print(f"  Service type: {result.get('service_type')}")
    print(f"  Immediate care: {result.get('immediate_care')}")
    print(f"  Recommendation: {result.get('recommendation_text', '')}")
    print(f"  Agent output: {result.get('agent_output', '')}")
    
    return result


def test_orientation(service_type=None, location=None):
    """Test orientation node"""
    print("\n" + "="*60)
    print("TEST 3: ORIENTATION NODE")
    print("="*60)
    
    # First get service type from triage if not provided
    if not service_type:
        triage_result = test_triage()
        service_type = triage_result.get('service_type')
    
    state = {
        "service_type": service_type,
        "user_location": location or TEST_LOCATION,
        "immediate_care": False
    }
    
    print(f"Input: service_type='{service_type}', location={state['user_location']}")
    print("\nRunning orientation node...")
    
    result = orientation_node(state)
    
    print(f"\n✅ Results:")
    print(f"  Found {len(result.get('nearby_facilities', []))} facilities")
    
    selected = result.get('selected_facility')
    if selected:
        print(f"\n  Nearest facility:")
        print(f"    Name: {selected.get('name')}")
        print(f"    Distance: {selected.get('distance')} km")
        print(f"    Address: {selected.get('address', 'N/A')}")
    
    print(f"\n  Agent output:\n{result.get('agent_output', '')}")
    
    return result


def test_mental_health_orientation():
    """Test orientation node with mental health input"""
    print("\n" + "="*60)
    print("TEST 4: MENTAL HEALTH → ORIENTATION")
    print("="*60)
    
    state = {
        "mental_health_recommendation": "emergency",  # or "therapist"
        "user_location": TEST_LOCATION,
        "service_type": ""  # Will be set by orientation node
    }
    
    print(f"Input: mental_health_recommendation='{state['mental_health_recommendation']}'")
    print("\nRunning orientation node...")
    
    result = orientation_node(state)
    
    print(f"\n✅ Results:")
    print(f"  Service type: {result.get('service_type', 'N/A')}")
    print(f"  Found {len(result.get('nearby_facilities', []))} facilities")
    print(f"\n  Agent output:\n{result.get('agent_output', '')}")
    
    return result


def test_full_flow_without_diagnosis():
    """Test extraction → triage → orientation (skipping diagnosis)"""
    print("\n" + "="*60)
    print("TEST 5: FULL FLOW (EXTRACTION → TRIAGE → ORIENTATION)")
    print("="*60)
    
    # Step 1: Extraction
    print("\n[Step 1] Extraction...")
    state = {
        "user_input": TEST_USER_INPUT,
        "symptoms": [],
        "negative_symptoms": []
    }
    state = extraction_node(state)
    print(f"  Extracted symptoms: {state.get('symptoms', [])}")
    
    # Step 2: Skip diagnosis - manually set disease/severity
    print("\n[Step 2] Skipping diagnosis - using manual values...")
    state["disease"] = TEST_DISEASE
    state["severity"] = TEST_SEVERITY
    print(f"  Using: disease='{state['disease']}', severity='{state['severity']}'")
    
    # Step 3: Triage
    print("\n[Step 3] Triage...")
    triage_result = triage_node(state)
    # Merge triage results into state
    state.update(triage_result)
    print(f"  Service type: {state.get('service_type')}")
    
    # Step 4: Orientation
    print("\n[Step 4] Orientation...")
    state["user_location"] = TEST_LOCATION
    orientation_result = orientation_node(state)
    # Merge orientation results into state
    state.update(orientation_result)
    
    print(f"\n✅ Final Results:")
    print(f"  Service type: {state.get('service_type')}")
    selected = state.get('selected_facility')
    if selected:
        print(f"  Nearest facility: {selected.get('name')} ({selected.get('distance')} km)")
    print(f"\n  Final output:\n{state.get('agent_output', '')}")
    
    return state


def test_stay_home():
    """Test STAY_HOME recommendation"""
    print("\n" + "="*60)
    print("TEST 6: STAY_HOME RECOMMENDATION")
    print("="*60)
    
    state = {
        "service_type": "STAY_HOME",
        "user_location": TEST_LOCATION
    }
    
    print(f"Input: service_type='STAY_HOME'")
    print("\nRunning orientation node...")
    
    result = orientation_node(state)
    
    print(f"\n✅ Results:")
    print(f"  Agent output:\n{result.get('agent_output', '')}")
    
    return result


if __name__ == "__main__":
    print("\n🧪 TESTING TRIAGE NODES (WITHOUT DIAGNOSIS)")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Test input: {TEST_USER_INPUT}")
    print(f"  Test disease: {TEST_DISEASE}")
    print(f"  Test severity: {TEST_SEVERITY}")
    print(f"  Test location: {TEST_LOCATION}")
    print("\n" + "="*60)
    
    try:
        # Test individual nodes
        extraction_result = test_extraction()
        
        # Test triage with different diseases/severities
        test_triage("flu", "mild")
        test_triage("flu", "severe")
        test_triage("chest pain", "severe")
        
        # Test orientation
        test_orientation("PHARMACY", TEST_LOCATION)
        test_orientation("HOSPITAL", TEST_LOCATION)
        
        # Test mental health
        test_mental_health_orientation()
        
        # Test STAY_HOME
        test_stay_home()
        
        # Test full flow
        test_full_flow_without_diagnosis()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

