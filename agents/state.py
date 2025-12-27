from typing import TypedDict, Optional, Dict, Any, List


class AgentState(TypedDict, total=False):
    # user input
    user_input: str
    intent: Optional[str]
    user_location: Optional[tuple]
    user_input_location: Optional[str]

    # conversation memory
    messages: List[Dict[str, str]]

    # agent control
    current_agent: Optional[str]
    next_agent: Optional[str]
    agent_output: Optional[str]
    should_end: Optional[bool]

    # system awareness
    agent_registry: Dict[str, Dict]

    # metadata / audit
    metadata: Dict[str, Any]
    
    # Triage workflow fields
    symptoms: List[str]
    negative_symptoms: List[str]
    extraction_result: Optional[Dict[str, Any]]
    disease: Optional[str]
    severity: Optional[str]
    confidence: Optional[float]
    service_type: Optional[str]
    immediate_care: Optional[bool]
    recommendation_text: Optional[str]
    nearby_facilities: List[Dict[str, Any]]
    selected_facility: Optional[Dict[str, Any]]
    
    # Diagnosis Q&A fields
    diagnosis_session_id: Optional[str]
    pending_questions: List[str]
    diagnosis_complete: Optional[bool]
    
    # Mental health integration
    mental_health_recommendation: Optional[str]
