# agents/triage_agent/workflow.py
"""
Triage workflow that chains extraction -> diagnosis -> triage -> orientation nodes
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

from .nodes import (
    extraction_node,
    diagnosis_node,
    triage_node,
    orientation_node
)


def triage_workflow(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Complete triage workflow:
    1. Extract symptoms
    2. Identify disease (diagnosis)
    3. Determine facility type (triage)
    4. Find nearest facility (orientation)
    """
    logger.info("🔄 Starting triage workflow")
    
    try:
        # Step 1: Extract symptoms
        logger.info("Step 1: Extraction")
        state = extraction_node(state)
        
        # Step 2: Identify disease
        logger.info("Step 2: Diagnosis")
        state = diagnosis_node(state)
        
        # Step 3: Determine facility type
        logger.info("Step 3: Triage")
        state = triage_node(state)
        
        # Step 4: Find nearest facility
        logger.info("Step 4: Orientation")
        state = orientation_node(state)
        
        # Format final output
        service_type = state.get("service_type", "UNKNOWN")
        selected_facility = state.get("selected_facility")
        
        if selected_facility:
            facility_name = selected_facility.get("name", "Unknown")
            distance = selected_facility.get("distance", 0)
            address = selected_facility.get("address", "")
            
            output = (
                f"Based on your symptoms, I recommend visiting a **{service_type}**.\n\n"
                f"📍 **Nearest facility:** {facility_name}\n"
                f"📏 **Distance:** {distance:.2f} km\n"
            )
            if address:
                output += f"📍 **Address:** {address}\n"
            
            if state.get("immediate_care"):
                output += "\n⚠️ **This requires immediate care - please seek help right away.**"
        elif service_type == "STAY_HOME":
            output = (
                "Based on your symptoms, you can **stay home and rest**.\n\n"
                "Your condition appears to be mild and self-limiting. "
                "Monitor your symptoms and seek medical care if they worsen."
            )
        else:
            output = (
                f"Based on your symptoms, I recommend visiting a **{service_type}**.\n\n"
                "Please provide your location to find the nearest facility."
            )
        
        state["agent_output"] = output
        state["current_agent"] = "triage"
        state["should_end"] = True
        
        logger.info("✅ Triage workflow completed")
        return state
        
    except Exception as e:
        logger.error(f"Error in triage workflow: {e}", exc_info=True)
        state["agent_output"] = f"Error in triage workflow: {str(e)}"
        state["current_agent"] = "triage"
        state["should_end"] = True
        return state

