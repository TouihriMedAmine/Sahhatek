# agents/triage_agent/agent.py
"""
Triage Agent for LangGraph Integration
Integrates the triage/logic.py functionality into the langgraph agent framework.
Handles symptom extraction, diagnosis, and healthcare recommendations using a knowledge base.
"""

from __future__ import annotations
import os
import sys
import re
import time
import json
import logging
from typing import Dict, Any, List, Optional, TypedDict, Tuple
from dataclasses import dataclass
from pathlib import Path

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import httpx
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# Import knowledge base
from .knowledge_base import get_knowledge_base

# LangSmith Integration
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    def traceable(*args, **kwargs):
        """Fallback decorator if LangSmith not available"""
        def decorator(func):
            return func
        return decorator if not callable(args[0]) else decorator(args[0])

# Import LangSmith decorators for better tracing
try:
    from agents.langsmith_decorators import trace_agent_node, add_metadata_to_state
except ImportError:
    # Fallback if langsmith_decorators not available
    def trace_agent_node(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not callable(args[0]) else decorator(args[0])
    def add_metadata_to_state(state, *args, **kwargs):
        return state

logger = logging.getLogger(__name__)

# Store for LangSmith logging
_triage_events = []

def log_to_langsmith(event_name: str, payload: dict):
    """
    Log triage events to LangSmith for observability.
    Events: symptom_extraction, diagnosis_generated, question_asked, answer_processed, 
            recommendation_generated, emergency_detected
    """
    global _triage_events
    _triage_events.append({
        "event": event_name,
        "data": payload,
        "timestamp": time.time()
    })

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================
API_KEY = os.getenv("HEALTHCARE_API_KEY", "sk-181c41d701ea417b90694f49adebd97d")
BASE_URL = os.getenv("HEALTHCARE_BASE_URL", "https://tokenfactory.esprit.tn/api")

# Initialize global clients
_http_client = None
_geolocator = None
_symptom_extractor_instance = None
_llm_client = None

# Global diagnostic sessions storage (use Redis/DB in production)
diagnostic_sessions: Dict[str, Dict] = {}

# ============================================================
# STATE MANAGEMENT (LangGraph Compatible)
# ============================================================
class TriageAgentState(TypedDict, total=False):
    """Enhanced state for triage agent workflow"""
    user_input: str
    agent_output: Optional[str]
    current_agent: str
    next_agent: Optional[str]
    metadata: Dict[str, Any]
    messages: List[Dict[str, str]]
    
    # Triage-specific fields
    session_id: Optional[str]
    symptoms: List[str]
    age_group: Optional[str]
    diagnoses: List[Dict[str, Any]]
    healthcare_recommendation: Optional[Dict[str, Any]]
    nearby_facilities: List[Dict[str, Any]]
    user_location: Optional[tuple]
    extraction_result: Optional[Dict[str, Any]]
    diagnosis_result: Optional[Dict[str, Any]]
    confidence_score: float
    severity: Optional[str]

@dataclass
class DiagnosisResult:
    """Result from diagnosis model"""
    diagnoses: List[Dict[str, Any]]
    questions: List[str]
    confidence_reached: bool
    top_confidence: float

# ============================================================
# CLIENT INITIALIZATION
# ============================================================
def get_http_client() -> Optional[httpx.Client]:
    """Get or create HTTP client"""
    global _http_client
    if _http_client is None:
        try:
            _http_client = httpx.Client(verify=False, timeout=30)
            logger.info("✅ HTTP client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize HTTP client: {e}")
    return _http_client

def get_geolocator() -> Optional[Nominatim]:
    """Get or create geolocator"""
    global _geolocator
    if _geolocator:
        return _geolocator
    _geolocator = Nominatim(user_agent="unified_healthcare")
    return _geolocator

def get_symptom_extractor():
    """
    DEPRECATED: Symptom extraction now uses LLM instead of NER.
    This function is kept for backward compatibility but always returns None.
    """
    global _symptom_extractor_instance
    if _symptom_extractor_instance is not None:
        return _symptom_extractor_instance
    
    # No longer using NER - LLM-based extraction is used instead
    logger.debug("Symptom extractor not needed - using LLM-based extraction")
    _symptom_extractor_instance = None
    return None

def get_llm_client():
    """Get or create LLM client for healthcare recommendations"""
    global _llm_client
    if _llm_client is not None:
        return _llm_client
    
    # Try Groq first if API key is set
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key and groq_key.strip():
        try:
            from groq import Groq
            _llm_client = Groq(api_key=groq_key)
            logger.info("✅ LLM client (Groq) initialized")
            return _llm_client
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize Groq client: {e}")
    
    # Fallback to OpenAI client (custom API)
    try:
        import httpx
        http_client = httpx.Client(verify=False)
        from openai import OpenAI
        _llm_client = OpenAI(api_key=API_KEY, base_url=BASE_URL, http_client=http_client)
        logger.info("✅ LLM client (OpenAI) initialized")
    except Exception as e2:
        logger.error(f"❌ Failed to initialize LLM clients: {e2}")
        _llm_client = None
    
    return _llm_client

# ============================================================
# UTILITY FUNCTIONS
# ============================================================
def normalize_symptom(s: str) -> str:
    """Normalize symptom string"""
    try:
        from .diagnosis_utils import normalize_symptom as normalize_func
        return normalize_func(s)
    except Exception:
        return s.lower().strip()

def geocode_location(location_str: str) -> tuple:
    """Convert address to latitude/longitude"""
    geolocator = get_geolocator()
    if not geolocator:
        return None, None
    
    try:
        if ',' in location_str:
            parts = location_str.split(',')
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        return lat, lon
                except ValueError:
                    pass
        
        location = geolocator.geocode(location_str)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        logger.error(f"Error geocoding location: {e}")
        return None, None

def find_nearby_facilities(lat: float, lon: float, facility_type: str, radius_km: int = 5) -> List[Dict]:
    """Find nearby healthcare facilities using Overpass API"""
    if not lat or not lon:
        return []
    
    service_type_map = {
        "PHARMACY": "pharmacy",
        "DOCTOR": "doctors",
        "HOSPITAL": "hospital",
        "CLINIC": "clinic",
        "URGENT_CARE": "hospital",
        "MENTAL_HEALTH": "hospital",
        "PSYCHIATRIST": "hospital",  # Psychiatrists are usually in hospitals/clinics
        "STAY_HOME": None
    }
    
    amenity_tag = service_type_map.get(facility_type.upper())
    if not amenity_tag:
        return []
    
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    if facility_type.upper() in ["MENTAL_HEALTH", "URGENT_CARE", "PSYCHIATRIST"]:
        query = f"""
        [out:json][timeout:25];
        (
          node["amenity"~"^(hospital|clinic)$"](around:{radius_km * 1000},{lat},{lon});
          way["amenity"~"^(hospital|clinic)$"](around:{radius_km * 1000},{lat},{lon});
          relation["amenity"~"^(hospital|clinic)$"](around:{radius_km * 1000},{lat},{lon});
        );
        out center;
        """
    else:
        query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="{amenity_tag}"](around:{radius_km * 1000},{lat},{lon});
          way["amenity"="{amenity_tag}"](around:{radius_km * 1000},{lat},{lon});
          relation["amenity"="{amenity_tag}"](around:{radius_km * 1000},{lat},{lon});
        );
        out center;
        """
    
    try:
        client = get_http_client()
        if not client:
            return []
        
        # Retry logic for Overpass API
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = client.post(overpass_url, content=query, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    break
                elif response.status_code == 504:
                    logger.warning(f"Overpass API timeout (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(1)  # Wait before retry
                        continue
                    return []
                else:
                    logger.warning(f"Overpass API returned status {response.status_code}")
                    return []
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Overpass API error (attempt {attempt + 1}/{max_retries}): {e}")
                    import time
                    time.sleep(1)
                    continue
                else:
                    raise
        
        places = []
        for element in data.get("elements", []):
            if "tags" in element:
                tags = element["tags"]
                name = tags.get("name", "Unknown")
                amenity = tags.get("amenity", "")
                
                if facility_type.upper() in ["PHARMACY", "DOCTOR", "HOSPITAL", "CLINIC"]:
                    if amenity != amenity_tag:
                        continue
                
                if "lat" in element and "lon" in element:
                    place_lat, place_lon = element["lat"], element["lon"]
                elif "center" in element:
                    place_lat, place_lon = element["center"]["lat"], element["center"]["lon"]
                else:
                    continue
                
                distance = geodesic((lat, lon), (place_lat, place_lon)).kilometers
                
                places.append({
                    "name": name,
                    "type": amenity,
                    "distance": round(distance, 2),
                    "latitude": place_lat,
                    "longitude": place_lon,
                    "address": tags.get("addr:full") or tags.get("addr:street", "")
                })
        
        places.sort(key=lambda x: x["distance"])
        return places[:5]
    except Exception as e:
        logger.error(f"Error finding nearby facilities: {e}")
        return []

def get_healthcare_recommendation(illness: str, severity: str = "") -> Dict:
    """Get healthcare service recommendation using LLM with rule-based fallback"""
    
    illness_lower = illness.lower()
    
    # Rule-based recommendations
    stay_home_conditions = [
        'flu', 'influenza', 'common cold', 'cold', 'viral infection',
        'mild headache', 'mild fever', 'runny nose', 'sneezing',
        'mild sore throat', 'mild cough', 'mild fatigue'
    ]
    
    pharmacy_conditions = [
        'mild pain', 'headache', 'mild allergy', 'mild skin irritation',
        'mild indigestion', 'mild heartburn', 'mild constipation',
        'mild diarrhea', 'mild nausea'
    ]
    
    # Check conditions
    for condition in stay_home_conditions:
        if condition in illness_lower:
            if severity.lower() in ['mild', 'minor', '']:
                return {
                    "service_type": "STAY_HOME",
                    "immediate_care": False,
                    "recommendation_text": "Rest at home with supportive care"
                }
            elif severity.lower() in ['moderate', 'severe']:
                return {
                    "service_type": "PHARMACY",
                    "immediate_care": False,
                    "recommendation_text": "Visit pharmacy for medication"
                }
    
    for condition in pharmacy_conditions:
        if condition in illness_lower:
            if severity.lower() in ['mild', 'minor', '']:
                return {
                    "service_type": "PHARMACY",
                    "immediate_care": False,
                    "recommendation_text": "OTC medication recommended"
                }
    
    # Fallback to LLM
    client = get_llm_client()
    if not client:
        return {"service_type": "DOCTOR", "immediate_care": False, "recommendation_text": "Consult a doctor"}
    
    system_message = """You are a medical triage assistant. Recommend healthcare service.
Respond with: SERVICE_TYPE|IMMEDIATE_CARE
SERVICE_TYPE ∈ {PHARMACY, DOCTOR, HOSPITAL, MENTAL_HEALTH, CLINIC, URGENT_CARE, STAY_HOME}
IMMEDIATE_CARE ∈ {YES, NO}"""
    
    user_message = f"Illness: {illness}\nSeverity: {severity or 'mild'}"
    
    try:
        if hasattr(client, 'chat'):
            # Groq or OpenAI style
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=50
            )
            recommendation_text = response.choices[0].message.content.strip()
        else:
            return {"service_type": "DOCTOR", "immediate_care": False}
        
        parts = recommendation_text.split("|")
        service_type = parts[0].strip().upper() if parts else "DOCTOR"
        immediate_care = len(parts) > 1 and parts[1].strip().upper() == "YES"
        
        # Validate
        valid_types = ["PHARMACY", "DOCTOR", "HOSPITAL", "MENTAL_HEALTH", "CLINIC", "URGENT_CARE", "STAY_HOME"]
        if service_type not in valid_types:
            service_type = "DOCTOR"
        
        return {
            "service_type": service_type,
            "immediate_care": immediate_care,
            "recommendation_text": recommendation_text
        }
    except Exception as e:
        logger.error(f"Error getting recommendation: {e}")
        if severity.lower() in ['mild', 'minor']:
            return {"service_type": "PHARMACY", "immediate_care": False}
        return {"service_type": "DOCTOR", "immediate_care": False}

# ============================================================
# Q&A FUNCTION
# ============================================================
def answer_triage_question(state: Dict[str, Any]) -> Dict[str, Any]:
    """Answer a question about triage, symptoms, or healthcare using knowledge base"""
    try:
        kb = get_knowledge_base()
        user_input = state.get("user_input", "")
        
        if not user_input:
            return {
                "qa_response": "Please provide a question about symptoms or healthcare.",
                "agent_output": "Q&A requested but no input provided"
            }
        
        # Build context from triage state if available
        context_parts = []
        if state.get("diagnoses"):
            context_parts.append(f"Patient diagnoses: {[d.get('name') for d in state.get('diagnoses', [])]}")
        if state.get("symptoms"):
            context_parts.append(f"Reported symptoms: {', '.join(state.get('symptoms', []))}")
        if state.get("age_group"):
            context_parts.append(f"Age group: {state.get('age_group')}")
        
        context = "\n".join(context_parts) if context_parts else None
        
        # Answer question using knowledge base
        response = kb.answer_question(user_input, context)
        
        return {
            "qa_response": response,
            "agent_output": "Q&A answered from knowledge base"
        }
    except Exception as e:
        logger.error(f"Error answering question: {e}")
        return {
            "qa_response": f"Error processing question: {str(e)}",
            "agent_output": f"Q&A error: {str(e)}"
        }

# ============================================================
# CORE TRIAGE AGENT FUNCTIONS
# ============================================================
@traceable(name="⚕️_Triage_01_ExtractSymptoms", run_type="chain")
def extract_symptoms(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract symptoms from user input using LLM, including both positive and negative symptoms.
    LangSmith tracks: symptom_extraction event with extraction method and results.
    """
    try:
        user_input = state.get("user_input", "")
        if not user_input:
            return {
                "extraction_result": None,
                "symptoms": [],
                "negative_symptoms": [],
                "agent_output": "Please provide symptom information"
            }
        
        logger.info(f"🔍 Extracting symptoms from: '{user_input[:100]}' using LLM")
        
        # Use LLM to extract symptoms
        llm_client = get_llm_client()
        if not llm_client:
            logger.warning("⚠️ LLM client not available, using fallback")
            symptoms = [s.strip() for s in user_input.split(",") if s.strip()]
            return {
                "extraction_result": {"method": "fallback"},
                "symptoms": symptoms,
                "negative_symptoms": [],
                "agent_output": f"Detected symptoms: {', '.join(symptoms)}"
            }
        
        # Get model name based on client type
        # Check if it's a Groq client by checking the type
        is_groq = 'groq' in str(type(llm_client)).lower() or hasattr(llm_client, 'models')
        if is_groq:
            # Use working Groq model
            model_name = "meta-llama/llama-4-scout-17b-16e-instruct"
        else:  # OpenAI-compatible client
            # Use a standard OpenAI model or fallback to Groq model
            model_name = "meta-llama/llama-4-scout-17b-16e-instruct"
        
        # Prompt for symptom extraction
        prompt = f"""Extract medical symptoms from the following user input. Identify:
1. Positive symptoms (symptoms the user HAS or mentions having)
2. Negative symptoms (symptoms the user explicitly DENIES having, e.g., "no fever", "I don't have headache")

User input: "{user_input}"

Return ONLY a valid JSON object with this exact structure:
{{
    "positive_symptoms": ["symptom1", "symptom2", ...],
    "negative_symptoms": ["symptom3", "symptom4", ...]
}}

Rules:
- Use canonical symptom names (e.g., "fever" not "high temperature", "headache" not "head pain")
- Normalize symptoms to lowercase
- Only include symptoms explicitly mentioned
- For negative symptoms, only include those explicitly denied (e.g., "no fever", "I don't have X")
- Return empty arrays if no symptoms found
- Do not include any text outside the JSON object"""

        try:
            if hasattr(llm_client, 'chat'):  # Groq or OpenAI client
                response = llm_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a medical symptom extraction assistant. Extract symptoms accurately and return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=500
                )
                content = response.choices[0].message.content.strip()
            else:
                # Fallback
                symptoms = [s.strip() for s in user_input.split(",") if s.strip()]
                return {
                    "extraction_result": {"method": "fallback"},
                    "symptoms": symptoms,
                    "negative_symptoms": [],
                    "agent_output": f"Detected symptoms: {', '.join(symptoms)}"
                }
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                positive_symptoms = result.get("positive_symptoms", [])
                negative_symptoms = result.get("negative_symptoms", [])
                
                # Normalize symptoms
                try:
                    from .diagnosis_utils import normalize_symptom as normalize_symptom_func
                    positive_symptoms = [normalize_symptom_func(s) for s in positive_symptoms if s]
                    negative_symptoms = [normalize_symptom_func(s) for s in negative_symptoms if s]
                except:
                    # Fallback normalization
                    positive_symptoms = [s.lower().strip().replace(" ", "_") for s in positive_symptoms if s]
                    negative_symptoms = [s.lower().strip().replace(" ", "_") for s in negative_symptoms if s]
                
                logger.info(f"✅ Extracted {len(positive_symptoms)} positive and {len(negative_symptoms)} negative symptoms")
                
                # Log to LangSmith: symptom extraction event
                log_to_langsmith("symptom_extraction", {
                    "method": "llm",
                    "positive_symptoms_count": len(positive_symptoms),
                    "negative_symptoms_count": len(negative_symptoms),
                    "positive_symptoms": positive_symptoms,
                    "negative_symptoms": negative_symptoms,
                    "user_input_length": len(user_input),
                    "success": True
                })
                
                return {
                    "extraction_result": {"method": "llm", "raw_response": content},
                    "symptoms": positive_symptoms,
                    "negative_symptoms": negative_symptoms,
                    "agent_output": f"Extracted {len(positive_symptoms)} positive and {len(negative_symptoms)} negative symptoms"
                }
            else:
                logger.warning(f"⚠️ Could not parse JSON from LLM response: {content[:200]}")
                # Fallback
                symptoms = [s.strip() for s in user_input.split(",") if s.strip()]
                
                # Log to LangSmith: fallback extraction
                log_to_langsmith("symptom_extraction", {
                    "method": "fallback_json_parse",
                    "positive_symptoms_count": len(symptoms),
                    "negative_symptoms_count": 0,
                    "positive_symptoms": symptoms,
                    "negative_symptoms": [],
                    "success": False,
                    "reason": "JSON parsing failed"
                })
                
                return {
                    "extraction_result": {"method": "fallback"},
                    "symptoms": symptoms,
                    "negative_symptoms": [],
                    "agent_output": f"Detected symptoms: {', '.join(symptoms)}"
                }
                
        except Exception as e:
            logger.error(f"Error calling LLM for symptom extraction: {e}", exc_info=True)
            # Fallback: simple parsing
            import re
            symptoms = [s.strip() for s in re.split(r",|\n|and", user_input) if s.strip()]
            
            # Log to LangSmith: exception fallback
            log_to_langsmith("symptom_extraction", {
                "method": "fallback_exception",
                "positive_symptoms_count": len(symptoms),
                "negative_symptoms_count": 0,
                "positive_symptoms": symptoms,
                "negative_symptoms": [],
                "success": False,
                "reason": str(e),
                "error_type": type(e).__name__
            })
            
            return {
                "extraction_result": {"method": "fallback", "error": str(e)},
                "symptoms": symptoms,
                "negative_symptoms": [],
                "agent_output": f"Detected symptoms: {', '.join(symptoms)}"
            }
    except Exception as e:
        logger.error(f"Error extracting symptoms: {e}")
        return {
            "extraction_result": None,
            "symptoms": [],
            "negative_symptoms": [],
            "agent_output": f"Error extracting symptoms: {str(e)}"
        }

@traceable(name="⚕️_Triage_02_StartDiagnosis", run_type="chain")
def start_diagnosis(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Start or update diagnostic session.
    LangSmith tracks: session creation/update with initial symptoms and age group.
    """
    try:
        session_id = state.get("session_id")
        symptoms_text = state.get("user_input", "")
        age_input = state.get("metadata", {}).get("age")
        
        # Check if session exists - if so, update it instead of creating new
        if session_id and session_id in diagnostic_sessions:
            session = diagnostic_sessions[session_id]
            logger.info(f"📋 Updating existing session {session_id}")
        else:
            # Create new session
            session_id = f"session_{int(time.time())}"
            logger.info(f"📋 Creating new session {session_id}")
        
        # Extract symptoms (both positive and negative)
        extraction_result = extract_symptoms(state)
        positive_symptoms = extraction_result.get("symptoms", [])
        negative_symptoms = extraction_result.get("negative_symptoms", [])
        
        # Determine age group
        user_age_group = None
        try:
            from .diagnosis_utils import normalize_symptom, determine_age_group
            user_age_group = determine_age_group(age_input) if age_input else None
        except Exception:
            user_age_group = "adult"
        
        # Initialize or update session
        if session_id not in diagnostic_sessions:
            # New session
            all_symptoms = positive_symptoms + [normalize_symptom(s) for s in positive_symptoms]
            diagnostic_sessions[session_id] = {
                "positive_symptoms": positive_symptoms.copy(),
                "negative_symptoms": negative_symptoms.copy(),
                "negative_diseases": set(),
                "asked_symptoms": set([normalize_symptom(s) for s in positive_symptoms]),
                "user_age_group": user_age_group,
                "turn": 0,
                "previous_conf": {},
                "expand_search": False
            }
        else:
            # Update existing session - merge symptoms
            session = diagnostic_sessions[session_id]
            for s in positive_symptoms:
                if s not in session["positive_symptoms"]:
                    session["positive_symptoms"].append(s)
                session["asked_symptoms"].add(normalize_symptom(s))
            
            for s in negative_symptoms:
                if s not in session["negative_symptoms"]:
                    session["negative_symptoms"].append(s)
                session["asked_symptoms"].add(normalize_symptom(s))
        
        # Log to LangSmith: session start/update event
        is_new_session = session_id not in diagnostic_sessions or session_id not in {s for s in diagnostic_sessions.keys() if diagnostic_sessions[s].get("turn") == 0}
        log_to_langsmith("diagnosis_session_started", {
            "session_id": session_id,
            "is_new_session": not is_new_session,  # True if update, False if new
            "age_group": user_age_group,
            "positive_symptoms_count": len(diagnostic_sessions[session_id]["positive_symptoms"]),
            "negative_symptoms_count": len(diagnostic_sessions[session_id]["negative_symptoms"]),
            "positive_symptoms": diagnostic_sessions[session_id]["positive_symptoms"],
            "negative_symptoms": diagnostic_sessions[session_id]["negative_symptoms"]
        })
        
        return {
            "session_id": session_id,
            "symptoms": diagnostic_sessions[session_id]["positive_symptoms"],
            "negative_symptoms": diagnostic_sessions[session_id]["negative_symptoms"],
            "age_group": user_age_group,
            "agent_output": f"Diagnostic session {'updated' if is_new_session else 'started'}. Symptoms: {', '.join(positive_symptoms)}"
        }
    except Exception as e:
        logger.error(f"Error starting diagnosis: {e}")
        return {
            "session_id": None,
            "symptoms": [],
            "negative_symptoms": [],
            "agent_output": f"Error starting diagnosis: {str(e)}"
        }

def generate_next_questions(state: Dict[str, Any], diagnoses: List[Dict]) -> Tuple[List[str], Dict[str, Any]]:
    """Generate ONE clarifying question at a time for multi-turn diagnosis"""
    try:
        from .diagnosis_utils import normalize_symptom, determine_age_group
        
        session_id = state.get("session_id")
        if not session_id or session_id not in diagnostic_sessions:
            return [], {}
        
        session = diagnostic_sessions[session_id]
        user_age_group = session.get("user_age_group")
        asked_symptoms = session.get("asked_symptoms", set())
        top_diagnoses = diagnoses[:5] if diagnoses else []
        
        questions = []
        logger.info(f"🤔 Generating clarifying questions (turn {session.get('turn', 0)})")
        
        # Strategy 1: Age-specific questions (only if early turn) - simplified
        if user_age_group and session.get('turn', 0) < 2:
            # Simple age-specific questions
            age_questions_map = {
                "child": ["Has there been any recent exposure to sick children?", "Is the child eating and drinking normally?"],
                "young": ["Have there been any recent work-related exposures?", "Are you taking any regular medications?"],
                "adult": ["Are you taking any regular medications?", "Have there been any recent travel?"],
                "old": ["Have you noticed any changes in memory?", "Are you taking multiple medications regularly?"]
            }
            age_questions = age_questions_map.get(user_age_group, [])
            for q in age_questions:
                if normalize_symptom(q) not in asked_symptoms:
                    questions.append(q)
                    asked_symptoms.add(normalize_symptom(q))
                    logger.info(f"  → Added age-specific question")
                    break
        
        # Strategy 2: Specific symptom questions from diagnoses (most important)
        if not questions:
            try:
                # Create a copy of asked_symptoms to avoid modifying the original during generation
                asked_symptoms_copy = set(asked_symptoms)
                
                logger.info(f"  📊 Asked symptoms: {list(asked_symptoms_copy)[:5]}")
                logger.info(f"  📊 Positive symptoms: {session.get('positive_symptoms', [])[:5]}")
                logger.info(f"  📊 Negative symptoms: {session.get('negative_symptoms', [])[:5]}")
                
                # Generate questions from canonical symptoms in diagnoses
                symptom_questions = []
                for diagnosis in top_diagnoses[:3]:  # Top 3 diagnoses
                    canonical_symptoms = diagnosis.get("canonical_symptoms", [])
                    for symptom in canonical_symptoms:
                        symptom_norm = normalize_symptom(symptom)
                        if symptom_norm not in asked_symptoms_copy:
                            question_text = f"Do you have {symptom.replace('_', ' ')}?"
                            symptom_questions.append(question_text)
                            asked_symptoms_copy.add(symptom_norm)
                            if len(symptom_questions) >= 5:
                                break
                    if len(symptom_questions) >= 5:
                        break
                
                logger.info(f"  📋 Generated {len(symptom_questions)} symptom questions")
                
                if symptom_questions:
                    # Filter out questions about symptoms we already know (positive or negative)
                    positive_symptoms_normalized = {normalize_symptom(s) for s in session.get("positive_symptoms", [])}
                    negative_symptoms_normalized = {normalize_symptom(s) for s in session.get("negative_symptoms", [])}
                    
                    filtered_questions = []
                    for q in symptom_questions:
                        # Extract symptom from question
                        symptom_text = q.replace("Do you have ", "").replace("?", "").strip().lower()
                        symptom_normalized = normalize_symptom(symptom_text)
                        
                        # Skip if already asked or known
                        if symptom_normalized not in asked_symptoms and \
                           symptom_normalized not in positive_symptoms_normalized and \
                           symptom_normalized not in negative_symptoms_normalized:
                            filtered_questions.append(q)
                            logger.info(f"    ✓ Valid question: {q}")
                        else:
                            logger.debug(f"    ✗ Skipped (already known/asked): {q}")
                    
                    if filtered_questions:
                        questions.append(filtered_questions[0])  # Only take first valid question
                        logger.info(f"  ✅ Added symptom-specific question: {filtered_questions[0]}")
                    else:
                        logger.warning(f"  ⚠️ All {len(symptom_questions)} questions were filtered out")
                else:
                    logger.warning(f"  ⚠️ No symptom questions generated from diagnoses")
            except Exception as e:
                logger.error(f"  ❌ Could not generate symptom questions: {e}", exc_info=True)
        
        # Strategy 3: General medical questions (fallback)
        if not questions:
            try:
                positive_symptoms = session.get("positive_symptoms", [])
                # Simple general questions based on symptoms
                general_questions = []
                if any("fever" in s or "temperature" in s for s in positive_symptoms):
                    general_questions.append("How long have you had the fever?")
                if any("pain" in s or "ache" in s for s in positive_symptoms):
                    general_questions.append("Is the pain constant or intermittent?")
                if any("cough" in s for s in positive_symptoms):
                    general_questions.append("Is the cough dry or productive?")
                if any("headache" in s for s in positive_symptoms):
                    general_questions.append("How severe is the headache on a scale of 1-10?")
                # Filter out already asked
                for q in general_questions:
                    if normalize_symptom(q) not in asked_symptoms:
                        questions.append(q)
                        asked_symptoms.add(normalize_symptom(q))
                        logger.info(f"  → Added general question")
                        session["expand_search"] = True
                        break  # Only need one question
            except Exception as e:
                logger.warning(f"  ⚠️ Could not generate general questions: {e}")
        
        # Strategy 4: Direct fallback - generate questions from diagnosis canonical symptoms
        if not questions and top_diagnoses:
            try:
                logger.info("  🔄 Trying direct fallback question generation")
                # Get canonical symptoms from top diagnosis
                top_diagnosis = top_diagnoses[0]
                canonical_symptoms = top_diagnosis.get("canonical_symptoms", [])
                
                positive_symptoms_normalized = {normalize_symptom(s) for s in session.get("positive_symptoms", [])}
                negative_symptoms_normalized = {normalize_symptom(s) for s in session.get("negative_symptoms", [])}
                
                for symptom in canonical_symptoms:
                    symptom_normalized = normalize_symptom(symptom)
                    # Skip if already asked or known
                    if symptom_normalized not in asked_symptoms and \
                       symptom_normalized not in positive_symptoms_normalized and \
                       symptom_normalized not in negative_symptoms_normalized:
                        question = f"Do you have {symptom}?"
                        questions.append(question)
                        asked_symptoms.add(symptom_normalized)
                        logger.info(f"  ✅ Generated fallback question: {question}")
                        break  # Only need one question
            except Exception as e:
                logger.warning(f"  ⚠️ Fallback question generation failed: {e}")
        
        # Return only ONE question
        if questions:
            question = questions[0]
            # Mark this symptom as asked
            symptom_text = question.replace("Do you have ", "").replace("?", "").strip().lower()
            session["asked_symptoms"].add(normalize_symptom(symptom_text))
            logger.info(f"  ✅ Selected question: {question}")
            return [question], {"questions": [question]}
        
        # No more questions available
        logger.info("  ⚠️ No more questions available")
        return [], {}
    
    except Exception as e:
        logger.error(f"Error generating questions: {e}")
        return [], {}

def process_question_answer(state: Dict[str, Any], question: str, answer: str) -> Dict[str, Any]:
    """Process user's answer to a clarifying question - handles free-text with multiple symptoms"""
    try:
        from .diagnosis_utils import normalize_symptom, determine_age_group
        
        session_id = state.get("session_id")
        if not session_id or session_id not in diagnostic_sessions:
            return {"agent_output": "No active session"}
        
        session = diagnostic_sessions[session_id]
        positive_symptoms = session.get("positive_symptoms", [])
        negative_symptoms = session.get("negative_symptoms", [])
        asked_symptoms = session.get("asked_symptoms", set())
        
        answer_lower = answer.lower().strip()
        
        # Check if it's a simple yes/no answer
        if answer_lower in ['yes', 'y', 'yeah', 'yep', 'sure', 'correct', 'right', 'affirmative']:
            # Yes answer - extract symptom from question
            symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
            logger.info(f"  ✅ Processing YES answer for question: '{question}'")
            logger.info(f"  📝 Extracting symptom from: '{symptom_text}'")
            
            # Use normalize_symptom directly (no need for NER on question text)
            canonical = normalize_symptom(symptom_text)
            logger.info(f"  ✓ Normalized symptom: {canonical}")
            
            if canonical not in positive_symptoms:
                positive_symptoms.append(canonical)
                logger.info(f"  ✅ Added to positive symptoms: {canonical}")
            else:
                logger.info(f"  ℹ️ Symptom already in positive symptoms: {canonical}")
            
            asked_symptoms.add(normalize_symptom(canonical))
            logger.info(f"  ✓ Added positive symptom from yes answer: {canonical}")
        
        elif answer_lower in ['no', 'n', 'nope', 'nah', 'negative', 'not', "don't", "do not", "don't have", "do not have"]:
            # No answer - extract symptom from question as negative
            symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
            logger.info(f"  ❌ Processing NO answer for question: '{question}'")
            logger.info(f"  📝 Extracting symptom from: '{symptom_text}'")
            
            # Use normalize_symptom directly (no need for NER on question text)
            canonical = normalize_symptom(symptom_text)
            logger.info(f"  ✓ Normalized symptom: {canonical}")
            
            if canonical not in negative_symptoms:
                negative_symptoms.append(canonical)
                logger.info(f"  ✅ Added to negative symptoms: {canonical}")
            else:
                logger.info(f"  ℹ️ Symptom already in negative symptoms: {canonical}")
            
            asked_symptoms.add(normalize_symptom(canonical))
            logger.info(f"  ✗ Added negative symptom from no answer: {canonical}")
        
        else:
            # Free-text answer - extract ALL symptoms (positive and negative) from the answer
            logger.info(f"  📝 Processing free-text answer: '{answer[:100]}'")
            
            # Extract symptoms from the answer text
            extraction_result = extract_symptoms({"user_input": answer})
            extracted_positive = extraction_result.get("symptoms", [])
            extracted_negative = extraction_result.get("negative_symptoms", [])
            
            # Add positive symptoms
            for symptom in extracted_positive:
                if symptom not in positive_symptoms:
                    positive_symptoms.append(symptom)
                asked_symptoms.add(normalize_symptom(symptom))
                logger.info(f"  ✓ Extracted positive symptom: {symptom}")
            
            # Add negative symptoms
            for symptom in extracted_negative:
                if symptom not in negative_symptoms:
                    negative_symptoms.append(symptom)
                asked_symptoms.add(normalize_symptom(symptom))
                logger.info(f"  ✗ Extracted negative symptom: {symptom}")
            
            # Also try to process the original question if answer doesn't contain explicit symptoms
            if not extracted_positive and not extracted_negative:
                # Fallback: simple extraction from question
                symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
                symptom_normalized = normalize_symptom(symptom_text)
                
                answer_lower = answer.lower().strip()
                if answer_lower in ['yes', 'y', 'yeah', 'yep', 'sure', 'correct', 'right', 'affirmative']:
                    if symptom_normalized not in positive_symptoms:
                        positive_symptoms.append(symptom_normalized)
                    asked_symptoms.add(symptom_normalized)
                    logger.info(f"  ✓ Added symptom from question: {symptom_normalized}")
                elif answer_lower in ['no', 'n', 'nope', 'nah', 'negative', 'not']:
                    if symptom_normalized not in negative_symptoms:
                        negative_symptoms.append(symptom_normalized)
                    asked_symptoms.add(symptom_normalized)
                    logger.info(f"  ✗ Added negative symptom from question: {symptom_normalized}")
        
        # Update session
        session["positive_symptoms"] = positive_symptoms
        session["negative_symptoms"] = negative_symptoms
        session["asked_symptoms"] = asked_symptoms
        
        logger.info(f"  📊 Session updated: {len(positive_symptoms)} positive, {len(negative_symptoms)} negative symptoms")
        logger.info(f"  📋 Positive symptoms: {positive_symptoms}")
        logger.info(f"  📋 Negative symptoms: {negative_symptoms}")
        
        return {
            "agent_output": "Answer processed",
            "symptoms": positive_symptoms.copy(),  # Return copy to ensure it's included
            "negative_symptoms": negative_symptoms.copy()  # Return copy to ensure it's included
        }
    
    except Exception as e:
        logger.error(f"Error processing answer: {e}", exc_info=True)
        return {"agent_output": f"Error processing answer: {str(e)}"}

@traceable(name="⚕️_Triage_03_GenerateDiagnosis", run_type="chain")
def generate_diagnosis(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate diagnosis from symptoms with multi-turn questioning until confident"""
    try:
        from .diagnosis_utils import normalize_symptom, determine_age_group
        
        session_id = state.get("session_id")
        if not session_id or session_id not in diagnostic_sessions:
            return {
                "diagnoses": [],
                "diagnosis_result": None,
                "pending_questions": [],
                "agent_output": "No active diagnostic session"
            }
        
        session = diagnostic_sessions[session_id]
        confidence_threshold = 0.85  # Slightly lower than 0.95 for LangGraph multi-turn
        max_turns = 5  # Limit iterations for LangGraph
        
        # Multi-turn questioning loop
        for turn in range(max_turns):
            session["turn"] = turn
            logger.info(f"\n📊 === DIAGNOSTIC TURN {turn + 1}/{max_turns} ===")
            
            # Generate diagnosis
            try:
                from .diagnosis_utils import generate_diagnosis_llm
                from .agent import get_llm_client
                
                llm_client = get_llm_client()
                diagnosis_data = generate_diagnosis_llm(
                    session["positive_symptoms"],
                    session["negative_symptoms"],
                    session["negative_diseases"],
                    session["user_age_group"],
                    session["expand_search"],
                    llm_client
                )
            except Exception as e:
                logger.error(f"Error generating diagnosis: {e}")
                return {
                    "diagnoses": [],
                    "diagnosis_result": None,
                    "pending_questions": [],
                    "agent_output": f"Error generating diagnosis: {str(e)}"
                }
            
            diagnoses = diagnosis_data.get("diagnoses", []) if diagnosis_data else []
            
            if not diagnoses:
                logger.warning("No diagnoses generated")
                return {
                    "diagnoses": [],
                    "diagnosis_result": None,
                    "pending_questions": [],
                    "agent_output": "Could not generate diagnoses"
                }
            
            # Log current diagnoses
            logger.info(f"📋 Top diagnoses (turn {turn + 1}):")
            for i, d in enumerate(diagnoses[:3], 1):
                logger.info(f"  {i}. {d['name']}: {d.get('confidence', 0):.2f}")
            
            # Check if we've reached confidence threshold
            top_confidence = diagnoses[0].get("confidence", 0)
            logger.info(f"🎯 Top confidence: {top_confidence:.2f} (threshold: {confidence_threshold})")
            
            if top_confidence >= confidence_threshold:
                logger.info("✅ CONFIDENCE THRESHOLD REACHED - DIAGNOSIS COMPLETE")
                
                # Log to LangSmith: diagnosis complete event
                log_to_langsmith("diagnosis_complete", {
                    "turn": turn + 1,
                    "top_diagnosis": diagnoses[0].get("name") if diagnoses else None,
                    "top_confidence": top_confidence,
                    "diagnoses_count": len(diagnoses),
                    "confidence_threshold": confidence_threshold,
                    "positive_symptoms_count": len(session.get("positive_symptoms", [])),
                    "negative_symptoms_count": len(session.get("negative_symptoms", [])),
                    "questions_asked": len(session.get("asked_questions", []))
                })
                
                return {
                    "diagnoses": diagnoses,
                    "diagnosis_result": diagnosis_data,
                    "confidence_score": top_confidence,
                    "pending_questions": [],
                    "diagnosis_complete": True,
                    "agent_output": f"Diagnosis complete with {len(diagnoses)} conditions identified"
                }
            
            # Not confident yet - generate clarifying questions
            if turn < max_turns - 1:  # Don't ask questions on last turn
                logger.info("❓ Confidence not reached - generating clarifying questions...")
                questions, _ = generate_next_questions(state, diagnoses)
                
                if questions:
                    # Only ask ONE question at a time
                    question = questions[0] if questions else None
                    if question:
                        logger.info(f"❓ Question to ask: {question}")
                        
                        # Log to LangSmith: question asked event
                        log_to_langsmith("question_asked", {
                            "turn": turn + 1,
                            "question": question,
                            "top_diagnosis": diagnoses[0].get("name") if diagnoses else None,
                            "current_confidence": top_confidence,
                            "diagnoses_count": len(diagnoses),
                            "positive_symptoms_count": len(session.get("positive_symptoms", [])),
                            "negative_symptoms_count": len(session.get("negative_symptoms", []))
                        })
                        
                        # Format user-friendly message with single question
                        user_message = (
                            f"I need to ask you a question to better understand your condition "
                            f"and provide an accurate diagnosis:\n\n"
                            f"{question}"
                        )
                        
                        # Return with pending questions (only one) - wait for user response
                        return {
                            "diagnoses": diagnoses,
                            "diagnosis_result": diagnosis_data,
                            "confidence_score": top_confidence,
                            "pending_questions": [question],  # Only one question
                            "diagnosis_complete": False,
                            "agent_output": user_message
                        }
                else:
                    logger.info("No more questions available")
                    continue  # Continue to next turn
            else:
                logger.info(f"⏱️ Max turns reached ({max_turns}) - stopping diagnosis")
                break
        
        # Return final diagnoses after max turns
        logger.info("🏁 Diagnosis process ended (max turns reached)")
        diagnoses = diagnosis_data.get("diagnoses", []) if diagnosis_data else []
        return {
            "diagnoses": diagnoses,
            "diagnosis_result": diagnosis_data,
            "confidence_score": diagnoses[0].get("confidence", 0) if diagnoses else 0,
            "pending_questions": [],
            "diagnosis_complete": True,
            "agent_output": f"Diagnosis complete (max turns reached)"
        }
    
    except Exception as e:
        logger.error(f"Error in generate_diagnosis: {e}")
        return {
            "diagnoses": [],
            "diagnosis_result": None,
            "pending_questions": [],
            "agent_output": f"Error: {str(e)}"
        }

@traceable(name="⚕️_Triage_04_RecommendCare", run_type="chain")
def recommend_care(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recommend appropriate healthcare service using knowledge base and triage output.
    LangSmith tracks: emergency detection, recommendation generation, facility search results.
    """
    try:
        kb = get_knowledge_base()
        diagnoses = state.get("diagnoses", [])
        symptoms = state.get("symptoms", [])
        severity = state.get("severity", "moderate")
        user_input = state.get("user_input", "")
        
        # Check for emergency indicators
        is_emergency, emergency_context = kb.is_emergency(user_input)
        if is_emergency:
            # Log to LangSmith: emergency detected event
            log_to_langsmith("emergency_detected", {
                "user_input": user_input[:200],
                "emergency_context": emergency_context,
                "diagnoses_count": len(diagnoses),
                "symptoms": symptoms[:5]
            })
            
            return {
                "healthcare_recommendation": {
                    "service_type": "HOSPITAL",
                    "immediate_care": True,
                    "recommendation_text": "EMERGENCY DETECTED - Seek immediate medical care!",
                    "emergency": True,
                    "guidance": emergency_context
                },
                "nearby_facilities": [],
                "agent_output": "🚨 EMERGENCY - Go to Hospital immediately!"
            }
        
        # Get primary illness from diagnoses
        if not diagnoses:
            primary_illness = ", ".join(symptoms[:3]) if symptoms else "unknown condition"
        else:
            primary_illness = diagnoses[0].get("name", "condition")
        
        # Get context from knowledge base
        kb_context = kb.get_recommendation_context(diagnoses, symptoms)
        
        # Get healthcare recommendation with KB context
        recommendation = get_healthcare_recommendation_with_kb(
            primary_illness, 
            severity,
            kb_context,
            diagnoses
        )
        
        # Get nearby facilities if location available
        nearby = []
        user_location = state.get("user_location")
        if user_location and user_location[0] and user_location[1]:
            nearby = find_nearby_facilities(
                user_location[0],
                user_location[1],
                recommendation.get("service_type", "DOCTOR")
            )
        
        # Add KB guidance to recommendation
        guidance_results = kb.retrieve(primary_illness, k=2)
        if guidance_results:
            recommendation["guidance"] = guidance_results[0].content
        
        # Log to LangSmith: recommendation generated event
        log_to_langsmith("recommendation_generated", {
            "primary_illness": primary_illness,
            "service_type": recommendation.get("service_type"),
            "immediate_care": recommendation.get("immediate_care", False),
            "severity": severity,
            "nearby_facilities_count": len(nearby),
            "top_diagnosis": diagnoses[0].get("name") if diagnoses else None,
            "top_confidence": diagnoses[0].get("confidence", 0) if diagnoses else 0,
            "kb_source": recommendation.get("kb_source", False)
        })
        
        return {
            "healthcare_recommendation": recommendation,
            "nearby_facilities": nearby,
            "agent_output": f"Recommendation: {recommendation.get('service_type')}. Found {len(nearby)} nearby facilities."
        }
    except Exception as e:
        logger.error(f"Error recommending care: {e}")
        return {
            "healthcare_recommendation": None,
            "nearby_facilities": [],
            "agent_output": f"Error: {str(e)}"
        }

def get_healthcare_recommendation_with_kb(illness: str, severity: str = "", kb_context: str = "", diagnoses: List[Dict] = None) -> Dict:
    """Get healthcare service recommendation using knowledge base"""
    kb = get_knowledge_base()
    
    illness_lower = illness.lower()
    
    # Extended rule-based recommendations from KB
    stay_home_conditions = [
        'flu', 'influenza', 'common cold', 'cold', 'viral infection', 'rsv', 'respiratory syncytial virus',
        'mild headache', 'mild fever', 'runny nose', 'sneezing', 'rhinovirus', 'coxsackievirus',
        'mild sore throat', 'mild cough', 'mild fatigue', 'viral rhinitis'
    ]
    
    pharmacy_conditions = [
        'mild pain', 'headache', 'mild allergy', 'mild skin irritation', 'allergic rhinitis',
        'mild indigestion', 'mild heartburn', 'mild constipation', 'allergies',
        'mild diarrhea', 'mild nausea', 'hay fever'
    ]
    
    doctor_conditions = [
        'sinusitis', 'sinus infection', 'bacterial infection', 'strep throat', 'pharyngitis',
        'otitis', 'ear infection', 'pneumonia', 'bronchitis', 'upper respiratory infection'
    ]
    
    # Check conditions for STAY_HOME
    for condition in stay_home_conditions:
        if condition in illness_lower:
            if severity.lower() in ['mild', 'minor', '']:
                # Get KB guidance
                results = kb.retrieve("STAY_HOME", k=1, category="recommendations")
                guidance = results[0].content if results else ""
                return {
                    "service_type": "STAY_HOME",
                    "immediate_care": False,
                    "recommendation_text": "Rest at home with supportive care",
                    "guidance": guidance,
                    "kb_source": True
                }
            elif severity.lower() in ['moderate', 'severe']:
                results = kb.retrieve("PHARMACY", k=1, category="recommendations")
                guidance = results[0].content if results else ""
                return {
                    "service_type": "PHARMACY",
                    "immediate_care": False,
                    "recommendation_text": "Visit pharmacy for medication",
                    "guidance": guidance,
                    "kb_source": True
                }
    
    # Check conditions for PHARMACY
    for condition in pharmacy_conditions:
        if condition in illness_lower:
            if severity.lower() in ['mild', 'minor', '']:
                results = kb.retrieve("PHARMACY", k=1, category="recommendations")
                guidance = results[0].content if results else ""
                return {
                    "service_type": "PHARMACY",
                    "immediate_care": False,
                    "recommendation_text": "OTC medication recommended",
                    "guidance": guidance,
                    "kb_source": True
                }
    
    # Check conditions for DOCTOR
    for condition in doctor_conditions:
        if condition in illness_lower:
            results = kb.retrieve("DOCTOR", k=1, category="recommendations")
            guidance = results[0].content if results else ""
            return {
                "service_type": "DOCTOR",
                "immediate_care": False,
                "recommendation_text": "Schedule appointment with doctor",
                "guidance": guidance,
                "kb_source": True
            }
    
    # For unmatched conditions, use KB retrieval as fallback (better than LLM which may fail)
    logger.info(f"Using KB retrieval for: {illness}")
    try:
        # Try to get recommendation from KB
        results = kb.retrieve(illness, k=1, category="recommendations")
        if results:
            guidance = results[0].content
            # Default to DOCTOR for unmatched conditions
            return {
                "service_type": "DOCTOR",
                "immediate_care": False,
                "recommendation_text": "Consult a doctor for evaluation",
                "guidance": guidance,
                "kb_source": True
            }
    except Exception as e:
        logger.warning(f"KB retrieval failed: {e}")
    
    # Final fallback: based on severity and confidence
    if diagnoses:
        top_confidence = diagnoses[0].get("confidence", 0)
        if top_confidence > 0.8:
            results = kb.retrieve("DOCTOR", k=1, category="recommendations")
            guidance = results[0].content if results else ""
            return {
                "service_type": "DOCTOR",
                "immediate_care": False,
                "recommendation_text": "Consult a doctor for confirmed diagnosis",
                "guidance": guidance,
                "kb_source": True
            }
    
    # Ultimate fallback
    if severity.lower() in ['severe', 'critical', 'emergency']:
        return {
            "service_type": "HOSPITAL",
            "immediate_care": True,
            "recommendation_text": "Seek immediate medical care at hospital"
        }
    elif severity.lower() in ['moderate']:
        results = kb.retrieve("DOCTOR", k=1, category="recommendations")
        guidance = results[0].content if results else ""
        return {
            "service_type": "DOCTOR",
            "immediate_care": False,
            "recommendation_text": "Schedule appointment with doctor",
            "guidance": guidance,
            "kb_source": True
        }
    else:
        results = kb.retrieve("PHARMACY", k=1, category="recommendations")
        guidance = results[0].content if results else ""
        return {
            "service_type": "PHARMACY",
            "immediate_care": False,
            "recommendation_text": "OTC medication may help",
            "guidance": guidance,
            "kb_source": True
        }

# ============================================================
# MAIN TRIAGE AGENT (for LangGraph integration)
# ============================================================
@trace_agent_node("triage_agent", "⚕️_Triage_Agent_Main")
def triage_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main triage agent that orchestrates symptom analysis and healthcare recommendations.
    Uses knowledge base for context-aware recommendations.
    Supports multi-turn questioning to reach confidence threshold before recommending care.
    Designed to work with LangGraph state management.
    LangSmith Tracing: Captures all symptom analysis, diagnosis generation, and care recommendations.
    """
    logger.info("🏥 TRIAGE AGENT ACTIVATED")
    
    try:
        kb = get_knowledge_base()
        user_input = state.get("user_input", "")
        session_id = state.get("session_id")
        metadata = state.get("metadata", {})
        
        # Check for pending questions from previous turn
        pending_questions = state.get("pending_questions", [])
        
        # Check if user input is a short answer (yes/no)
        is_short_answer = user_input.lower().strip() in ['yes', 'y', 'no', 'n', 'yeah', 'yep', 'nope', 'nah', 'sure', 'correct', 'right', 'negative', 'affirmative']
        
        # If we have a short answer, we MUST find the question and session_id from messages
        if is_short_answer:
            messages = state.get("messages", [])
            logger.info(f"🔍 Short answer detected, searching {len(messages)} messages for question and session_id...")
            
            # Search messages for session_id and pending_questions
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    try:
                        # Get metadata (handle both dict and JSON string)
                        msg_metadata = None
                        if isinstance(msg.get("metadata"), dict):
                            msg_metadata = msg["metadata"]
                        elif isinstance(msg.get("metadata"), str) and msg.get("metadata"):
                            import json
                            msg_metadata = json.loads(msg["metadata"])
                        
                        if msg_metadata:
                            # Get session_id
                            if not session_id:
                                found_session_id = msg_metadata.get("session_id")
                                if found_session_id:
                                    session_id = found_session_id
                                    state["session_id"] = session_id
                                    logger.info(f"🔍 Found session_id in message metadata: {session_id}")
                            
                            # Get pending_questions
                            if not pending_questions:
                                msg_pending = msg_metadata.get("pending_questions", [])
                                if msg_pending:
                                    pending_questions = msg_pending
                                    logger.info(f"🔍 Found pending questions in metadata: {pending_questions}")
                            
                        # ALWAYS try to extract question from content (even if metadata wasn't found)
                        # This is critical for short answers like "yes"/"no"
                        if not pending_questions:
                            content = msg.get("content", "")
                            logger.info(f"  🔍 Checking message content (length: {len(content)}): '{content[:150]}...'")
                            
                            # Try multiple patterns to find the question
                            import re
                            question_patterns = [
                                r"Do you have [^?\n]+\?",  # Standard pattern, stop at newline
                                r"Do you have [^?]+\?",     # Standard pattern
                                r"Do you have .+\?",        # More permissive
                            ]
                            
                            for pattern in question_patterns:
                                question_match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
                                if question_match:
                                    question_text = question_match.group(0).strip()
                                    pending_questions = [question_text]
                                    logger.info(f"🔍 Found question in message content using pattern '{pattern}': {pending_questions[0]}")
                                    
                                    # Also try to get session_id from this message's metadata if we haven't found it
                                    if not session_id and msg_metadata:
                                        found_session_id = msg_metadata.get("session_id")
                                        if found_session_id:
                                            session_id = found_session_id
                                            state["session_id"] = session_id
                                            logger.info(f"🔍 Found session_id from same message: {session_id}")
                                    break
                        
                        # If we found both, we can stop searching
                        if session_id and pending_questions:
                            break
                    except Exception as e:
                        logger.debug(f"Error processing message: {e}")
                        pass
        
        logger.info(f"🔍 Final check - pending_questions: {len(pending_questions)}, session_id: {session_id}")
        logger.info(f"🔍 Session exists: {session_id in diagnostic_sessions if session_id else False}")
        logger.info(f"🔍 User input: '{user_input}' (is_short_answer: {is_short_answer})")
        
        # CRITICAL: If we have a short answer and found a question, process it
        # Even if session_id is None, we can still extract the symptom from the question
        if is_short_answer and pending_questions:
            # If we don't have a valid session, try to find or create one
            if not session_id or session_id not in diagnostic_sessions:
                logger.warning(f"⚠️ Session not found ({session_id}), but have question - will process answer anyway")
                # Try to find session_id from all messages one more time
                messages = state.get("messages", [])
                for msg in reversed(messages):
                    if msg.get("role") == "assistant":
                        try:
                            if isinstance(msg.get("metadata"), dict):
                                found_id = msg["metadata"].get("session_id")
                                if found_id and found_id in diagnostic_sessions:
                                    session_id = found_id
                                    state["session_id"] = session_id
                                    logger.info(f"🔍 Found session_id on second pass: {session_id}")
                                    break
                        except:
                            pass
                
                # If still no session, we'll process without session (extract symptom from question)
                if not session_id or session_id not in diagnostic_sessions:
                    logger.warning("⚠️ No valid session found - will extract symptom from question directly")
                    # Extract symptom from question and process directly
                    question = pending_questions[0]
                    answer = user_input
                    
                    logger.info(f"📥 Processing answer '{answer}' to question '{question}' (no session)")
                    
                    # Extract symptom from question
                    symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
                    logger.info(f"  📝 Extracting symptom from question: '{symptom_text}'")
                    
                    # Use normalize_symptom directly (no NER needed)
                    canonical = normalize_symptom(symptom_text)
                    
                    logger.info(f"  ✓ Extracted symptom: {canonical}")
                    
                    # Process yes/no answer
                    answer_lower = answer.lower().strip()
                    if answer_lower in ['yes', 'y', 'yeah', 'yep', 'sure', 'correct', 'right', 'affirmative']:
                        # Add as positive symptom
                        state["symptoms"] = state.get("symptoms", []) + [canonical]
                        logger.info(f"  ✅ Added positive symptom: {canonical}")
                    elif answer_lower in ['no', 'n', 'nope', 'nah', 'negative', 'not']:
                        # Add as negative symptom
                        state["negative_symptoms"] = state.get("negative_symptoms", []) + [canonical]
                        logger.info(f"  ✗ Added negative symptom: {canonical}")
                    
                    # Now start/update diagnosis with this symptom
                    diagnosis = start_diagnosis(state)
                    state.update(diagnosis)
                    session_id = diagnosis.get("session_id")
                    
                    # Update session with the symptom
                    if session_id and session_id in diagnostic_sessions:
                        session = diagnostic_sessions[session_id]
                        if answer_lower in ['yes', 'y', 'yeah', 'yep', 'sure', 'correct', 'right', 'affirmative']:
                            if canonical not in session["positive_symptoms"]:
                                session["positive_symptoms"].append(canonical)
                        else:
                            if canonical not in session["negative_symptoms"]:
                                session["negative_symptoms"].append(canonical)
                    
                    # Continue with diagnosis
                    diagnosis_results = generate_diagnosis(state)
                    state.update(diagnosis_results)
                    
                    # Return next question or completion
                    if diagnosis_results.get("pending_questions"):
                        questions = diagnosis_results.get("pending_questions", [])
                        state["pending_questions"] = questions
                        state["agent_output"] = (
                            f"I need to ask you another question to better understand your condition:\n\n"
                            f"{questions[0]}"
                        )
                    elif diagnosis_results.get("diagnosis_complete"):
                        care_recommendation = recommend_care(state)
                        state.update(care_recommendation)
                    
                    state["current_agent"] = "triage"
                    return state
        
        # Process answer if we have pending questions and a valid session
        if pending_questions and session_id and session_id in diagnostic_sessions:
            logger.info(f"📥 Processing answer to pending question(s): {pending_questions}")
            
            # User's answer should be in user_input
            # Handle free-text answers that may contain multiple symptoms
            if user_input and len(pending_questions) > 0:
                # Process the first pending question's answer
                # The process_question_answer function will extract all symptoms from free-text
                question = pending_questions[0]
                answer = user_input
                
                logger.info(f"  Processing answer to: {question}")
                logger.info(f"  User answer: '{answer}'")
                process_result = process_question_answer(state, question, answer)
                state.update(process_result)
                
                # Always update session symptoms from process result (even if empty, to ensure sync)
                session = diagnostic_sessions[session_id]
                session["positive_symptoms"] = process_result.get("symptoms", [])
                session["negative_symptoms"] = process_result.get("negative_symptoms", [])
                state["symptoms"] = process_result.get("symptoms", [])
                state["negative_symptoms"] = process_result.get("negative_symptoms", [])
                
                logger.info(f"  📊 Updated state - Positive: {len(state.get('symptoms', []))}, Negative: {len(state.get('negative_symptoms', []))}")
                
                # Remove answered question from pending list
                pending_questions = pending_questions[1:]
                
                # Re-generate diagnosis with updated symptoms
                logger.info("🔄 Re-generating diagnosis with updated symptoms...")
                diagnosis_results = generate_diagnosis(state)
                state.update(diagnosis_results)
                
                # Check if diagnosis is complete
                if diagnosis_results.get("diagnosis_complete") and not diagnosis_results.get("pending_questions"):
                    logger.info("✅ Diagnosis complete - proceeding to care recommendation")
                    # Recommend care
                    care_recommendation = recommend_care(state)
                    state.update(care_recommendation)
                    state["current_agent"] = "triage"
                    return state
                else:
                    # Still asking questions - return ONE question at a time
                    logger.info(f"❓ More questions needed")
                    state["current_agent"] = "triage"
                    state["pending_questions"] = diagnosis_results.get("pending_questions", [])
                    # agent_output should already be set by generate_diagnosis with formatted question
                    if not state.get("agent_output") or "Generated" in state.get("agent_output", ""):
                        questions = diagnosis_results.get("pending_questions", [])
                        if questions:
                            # Only show the first question
                            state["agent_output"] = (
                                f"I need to ask you another question to better understand your condition:\n\n"
                                f"{questions[0]}"
                            )
                    return state
        
        # Check for emergency first
        is_emergency, emergency_guidance = kb.is_emergency(user_input)
        if is_emergency:
            logger.info("🚨 EMERGENCY DETECTED")
            return {
                "current_agent": "triage",
                "agent_output": "🚨 EMERGENCY DETECTED - Go to Hospital immediately!",
                "healthcare_recommendation": {
                    "service_type": "HOSPITAL",
                    "immediate_care": True,
                    "recommendation_text": "EMERGENCY - Seek immediate medical care!",
                    "emergency": True,
                    "guidance": emergency_guidance
                },
                "next_agent": None,  # Stop processing
                "session_id": session_id
            }
        
        # Check if this is a Q&A request vs. triage
        qa_keywords = ["what", "when", "how", "why", "explain", "tell", "describe", "question", "ask"]
        is_question = any(keyword in user_input.lower() for keyword in qa_keywords)
        
        if is_question and not any(symptom in user_input.lower() for symptom in ["have", "feel", "pain", "symptom"]):
            logger.info("💬 Q&A request detected")
            # Pure Q&A request
            qa_result = answer_triage_question(state)
            state.update(qa_result)
            state["current_agent"] = "triage"
            return state
        
        logger.info("🔍 Extracting symptoms from user input")
        # Extract symptoms
        extraction = extract_symptoms(state)
        state.update(extraction)
        
        # Start or update diagnosis if symptoms found
        if state.get("symptoms") or state.get("negative_symptoms"):
            logger.info("📋 Starting/updating diagnostic session")
            diagnosis = start_diagnosis(state)
            state.update(diagnosis)
            
            logger.info("🤖 Generating initial diagnosis")
            # Generate diagnoses with multi-turn questioning support
            diagnosis_results = generate_diagnosis(state)
            state.update(diagnosis_results)
            
            # Check if we have pending questions (need user input to continue)
            if diagnosis_results.get("pending_questions"):
                questions = diagnosis_results.get("pending_questions", [])
                logger.info(f"❓ {len(questions)} question(s) pending user response")
                state["current_agent"] = "triage"
                state["pending_questions"] = questions
                # agent_output should already be set by generate_diagnosis with formatted question
                # But ensure it's set if somehow missing
                if not state.get("agent_output") or "Generated" in state.get("agent_output", ""):
                    if questions:
                        # Only show the first question (should be only one anyway)
                        state["agent_output"] = (
                            f"I need to ask you a question to better understand your condition "
                            f"and provide an accurate diagnosis:\n\n"
                            f"{questions[0]}"
                        )
                return state
            
            # Diagnosis is complete - recommend care
            if diagnosis_results.get("diagnosis_complete"):
                logger.info("✅ Diagnosis complete - recommending care")
                care_recommendation = recommend_care(state)
                state.update(care_recommendation)
        
        state["current_agent"] = "triage"
        
        # Add LangSmith metadata
        state = add_metadata_to_state(state, "triage_agent", "processing", {
            "symptoms_found": len(state.get("symptoms", [])),
            "diagnoses_count": len(state.get("diagnoses", [])),
            "session_id": session_id,
            "has_pending_questions": len(pending_questions) > 0,
            "healthcare_recommendation": state.get("healthcare_recommendation", {}).get("service_type")
        })
        
        return state
    
    except Exception as e:
        logger.error(f"❌ Triage agent error: {e}", exc_info=True)
        state["agent_output"] = f"Triage agent error: {str(e)}"
        state["current_agent"] = "triage"
        
        # Add error metadata for LangSmith
        state = add_metadata_to_state(state, "triage_agent", "error", {
            "error_message": str(e),
            "error_type": type(e).__name__
        })
        
        return state
