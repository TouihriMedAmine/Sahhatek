
import json
import re
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

import httpx
from django.conf import settings
from openai import OpenAI
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# Logger
logger = logging.getLogger(__name__)

# CONFIG
# TODO: Move these to settings.py properly later
API_KEY = "sk-181c41d701ea417b90694f49adebd97d"
BASE_URL = "https://tokenfactory.esprit.tn/api"

# Initialize clients
_http_client = None
_openai_client = None
_geolocator = None
_symptom_extractor_instance = None

# Global state for diagnostic sessions
# In production, this should be in Redis or Database
diagnostic_sessions: Dict[str, Dict] = {}


def get_openai_client():
    global _http_client, _openai_client
    if _openai_client:
        return _openai_client
    
    try:
        _http_client = httpx.Client(verify=False)
        _openai_client = OpenAI(api_key=API_KEY, base_url=BASE_URL, http_client=_http_client)
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        return None
    return _openai_client

def get_geolocator():
    global _geolocator
    if _geolocator:
        return _geolocator
    try:
        _geolocator = Nominatim(user_agent="unified_healthcare")
    except Exception as e:
        logger.error(f"Failed to initialize Geolocator: {e}")
        return None
    return _geolocator

def get_symptom_extractor():
    global _symptom_extractor_instance
    if _symptom_extractor_instance:
        return _symptom_extractor_instance
        
    try:
        logger.info("🔧 Initializing SymptomExtractor (NER model)...")
        # Note: relative imports assume this file is in triage/logic.py
        try:
            from .src.extractor import SymptomExtractor
        except ImportError:
            # Fallback if package structure is different
            from triage.src.extractor import SymptomExtractor
            
        project_root = Path(__file__).parent
        model_path = project_root / "models" / "symptom_ner_spacy"
        symptom_dict_path = project_root / "data" / "symptom_dict.json"
        
        if model_path.exists() and symptom_dict_path.exists():
            _symptom_extractor_instance = SymptomExtractor(
                model_path=str(model_path),
                symptom_dict_path=str(symptom_dict_path)
            )
            logger.info("✅ Symptom extractor initialized successfully")
        else:
            logger.warning(f"⚠️ Model files not found at {model_path} or {symptom_dict_path}")
    except Exception as e:
        # Don't log full traceback for import errors to avoid noise if just missing files
        logger.error(f"❌ Could not initialize symptom extractor: {e}") 
        _symptom_extractor_instance = None
        
    return _symptom_extractor_instance

def wrap_normalize_symptom(s):
    try:
        try:
            from .diag import model
        except ImportError:
            from triage.diag import model
            
        return model.normalize_symptom(s)
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
    except:
        return None, None

def find_nearby_places(lat: float, lon: float, place_type: str, radius_km: int = 5) -> List[Dict]:
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
        "STAY_HOME": None
    }
    
    amenity_tag = service_type_map.get(place_type.upper())
    if not amenity_tag:
        return []
    
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    if place_type.upper() in ["MENTAL_HEALTH", "URGENT_CARE"]:
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
        response = httpx.post(overpass_url, data=query, timeout=10)
        data = response.json()
        
        places = []
        for element in data.get("elements", []):
            if "tags" in element:
                tags = element["tags"]
                name = tags.get("name", "Unknown")
                amenity = tags.get("amenity", "")
                
                if place_type.upper() in ["PHARMACY", "DOCTOR", "HOSPITAL", "CLINIC"]:
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
        logger.error(f"Error finding nearby places: {e}")
        return []

def get_healthcare_recommendation(illness: str, severity: str = "") -> Dict:
    """Get healthcare service recommendation using LLM with rule-based fallback"""
    
    # Rule-based recommendations for common conditions (more accurate)
    illness_lower = illness.lower()
    
    # STAY_HOME conditions - common viral illnesses that typically resolve on their own
    stay_home_conditions = [
        'flu', 'influenza', 'common cold', 'cold', 'viral infection', 
        'mild headache', 'mild fever', 'runny nose', 'sneezing',
        'mild sore throat', 'mild cough', 'mild fatigue'
    ]
    
    # PHARMACY conditions - minor issues that can be managed with OTC medications
    pharmacy_conditions = [
        'mild pain', 'headache', 'mild allergy', 'mild skin irritation',
        'mild indigestion', 'mild heartburn', 'mild constipation',
        'mild diarrhea', 'mild nausea', 'mild cold symptoms'
    ]
    
    # Check for stay home conditions first
    for condition in stay_home_conditions:
        if condition in illness_lower:
            if severity.lower() in ['mild', 'minor', '']:
                return {
                    "service_type": "STAY_HOME",
                    "immediate_care": False,
                    "recommendation_text": "STAY_HOME|NO"
                }
            elif severity.lower() in ['moderate', 'severe']:
                # Moderate/severe flu might need pharmacy or doctor
                return {
                    "service_type": "PHARMACY",
                    "immediate_care": False,
                    "recommendation_text": "PHARMACY|NO"
                }
    
    # Check for pharmacy conditions
    for condition in pharmacy_conditions:
        if condition in illness_lower:
            if severity.lower() in ['mild', 'minor', '']:
                return {
                    "service_type": "PHARMACY",
                    "immediate_care": False,
                    "recommendation_text": "PHARMACY|NO"
                }
    
    # Use LLM for other conditions
    client = get_openai_client()
    if not client:
        return {"service_type": "DOCTOR", "immediate_care": False}

    system_message = """You are a medical triage assistant. Recommend the most appropriate healthcare service.

Respond with ONLY: SERVICE_TYPE|IMMEDIATE_CARE

SERVICE_TYPE ∈ {PHARMACY, DOCTOR, HOSPITAL, MENTAL_HEALTH, CLINIC, URGENT_CARE, STAY_HOME}
IMMEDIATE_CARE ∈ {YES, NO}

DETAILED RULES:
1. STAY_HOME: Common viral illnesses (flu, cold) with mild symptoms, minor aches/pains, self-limiting conditions
   Examples: Mild flu, common cold, mild viral infection → STAY_HOME|NO

2. PHARMACY: Minor conditions treatable with over-the-counter medications
   Examples: Mild headache, mild allergy, mild skin issues, mild digestive problems → PHARMACY|NO

3. DOCTOR/CLINIC: Moderate conditions requiring professional evaluation but not urgent
   Examples: Persistent symptoms, moderate pain, chronic conditions, need for prescription → DOCTOR|NO or CLINIC|NO

4. URGENT_CARE: Urgent but not life-threatening, needs same-day care
   Examples: Severe pain, high fever, injury, acute illness → URGENT_CARE|YES/NO

5. HOSPITAL: Serious/life-threatening conditions, emergencies
   Examples: Chest pain, difficulty breathing, severe trauma, stroke symptoms → HOSPITAL|YES

6. MENTAL_HEALTH: Mental health or psychiatric conditions
   Examples: Depression, anxiety, mental health crisis → MENTAL_HEALTH|YES/NO

IMPORTANT: For common viral illnesses like flu or cold with mild/moderate severity, prefer STAY_HOME or PHARMACY, NOT CLINIC."""
    
    user_message = f"Illness: {illness}\nSeverity: {severity if severity else 'mild'}\n\nRespond with ONLY:\nSERVICE_TYPE|IMMEDIATE_CARE"
    
    try:
        response = client.chat.completions.create(
            model="hosted_vllm/Llama-3.1-70B-Instruct",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            max_tokens=50,
            top_p=0.9
        )
        
        recommendation_text = response.choices[0].message.content.strip()
        parts = recommendation_text.split("|")
        
        if len(parts) >= 2:
            service_type = parts[0].strip().upper()
            immediate_care = parts[1].strip().upper() == "YES"
        else:
            # Try to extract service type from the text
            service_type = parts[0].strip().upper() if parts else "DOCTOR"
            immediate_care = False
        
        # Validate and correct common mistakes
        valid_types = ["PHARMACY", "DOCTOR", "HOSPITAL", "MENTAL_HEALTH", "CLINIC", "URGENT_CARE", "STAY_HOME"]
        if service_type not in valid_types:
            # Try to find a valid type in the text
            for valid_type in valid_types:
                if valid_type in recommendation_text.upper():
                    service_type = valid_type
                    break
            else:
                # Default based on severity
                if severity.lower() in ['mild', 'minor']:
                    service_type = "PHARMACY"
                else:
                    service_type = "DOCTOR"
        
        # Post-process: For flu/cold with mild severity, ensure STAY_HOME or PHARMACY
        if any(term in illness_lower for term in ['flu', 'influenza', 'cold', 'viral']) and severity.lower() in ['mild', 'minor', '']:
            if service_type in ['CLINIC', 'DOCTOR']:
                service_type = "STAY_HOME"
                immediate_care = False
        
        return {
            "service_type": service_type,
            "immediate_care": immediate_care,
            "recommendation_text": recommendation_text
        }
    except Exception as e:
        logger.error(f"Error getting healthcare recommendation: {e}")
        # Fallback based on severity
        if severity.lower() in ['mild', 'minor']:
            return {"service_type": "PHARMACY", "immediate_care": False}
        return {"service_type": "DOCTOR", "immediate_care": False}

# Logic Functions

def extract_symptoms_logic(text: str):
    if not text:
        raise ValueError('Text is required')
    
    extractor = get_symptom_extractor()
    if not extractor:
        # Fallback if extractor fails to load
        logger.warning('Symptom extractor not available, using empty list')
        return {'symptoms': []}
    
    logger.info(f"🔍 Extracting symptoms from text: '{text[:100]}...'")
    result = extractor.extract(text)
    
    symptoms = result.get('symptoms', [])
    logger.info(f"✅ Extracted {len(symptoms)} symptoms: {[s.get('canonical', s.get('text', '')) for s in symptoms]}")
    
    return result

def start_diagnosis_logic(symptoms_text: str, age_input: str, session_id: Optional[str]):
    # Create new session if no session_id provided
    if not session_id or session_id not in diagnostic_sessions:
        session_id = f"session_{len(diagnostic_sessions)}_{int(time.time())}"
    
    # Extract symptoms if text provided
    positive_symptoms = []
    if symptoms_text:
        extractor = get_symptom_extractor()
        if extractor:
            logger.info(f"🔍 Using NER model to extract symptoms from: '{symptoms_text[:100]}...'")
            extraction_result = extractor.extract(symptoms_text)
            extracted = extraction_result.get('symptoms', [])
            positive_symptoms = [s['canonical'] for s in extracted if s.get('canonical')]
            logger.info(f"✅ NER extracted {len(positive_symptoms)} canonical symptoms: {positive_symptoms}")
        else:
            logger.warning("⚠️ Symptom extractor not available, using fallback text splitting")
            # Fallback: simple split
            positive_symptoms = [wrap_normalize_symptom(s) for s in re.split(r",|\n", symptoms_text) if s.strip()]
            logger.info(f"Fallback extracted {len(positive_symptoms)} symptoms: {positive_symptoms}")
    
    # Determine age group
    user_age_group = None
    try:
        try:
            from .diag import model
        except ImportError:
            from triage.diag import model
            
        user_age_group = model.determine_age_group(age_input) if age_input else None
    except:
        user_age_group = "adult" # Fallback

    # Initialize or update session
    session_exists = session_id in diagnostic_sessions
    
    if session_exists:
        # Update existing session
        session = diagnostic_sessions[session_id]
        if positive_symptoms:
            # Add new symptoms
            for symptom in positive_symptoms:
                normalized = wrap_normalize_symptom(symptom)
                if normalized not in [wrap_normalize_symptom(s) for s in session["positive_symptoms"]]:
                    session["positive_symptoms"].append(symptom)
                    session["asked_symptoms"].add(normalized)
        if user_age_group:
            session["user_age_group"] = user_age_group
    else:
        # Create new session
        diagnostic_sessions[session_id] = {
            "positive_symptoms": positive_symptoms,
            "negative_symptoms": [],
            "negative_diseases": set(),
            "asked_symptoms": set([wrap_normalize_symptom(s) for s in positive_symptoms]),
            "user_age_group": user_age_group,
            "turn": 0,
            "previous_conf": {},
            "expand_search": False
        }
    
    return {
        "session_id": session_id,
        "age_group": user_age_group or diagnostic_sessions[session_id].get("user_age_group"),
        "symptoms": diagnostic_sessions[session_id]["positive_symptoms"],
        "message": "Session updated" if session_exists else "Diagnostic session started"
    }

def diagnose_logic(session_id: str):
    if not session_id or session_id not in diagnostic_sessions:
        raise ValueError('Invalid session_id')
    
    session = diagnostic_sessions[session_id]
    turn = session["turn"]
    
    # Generate diagnosis
    logger.info(f"Generating diagnosis for session {session_id}, turn {turn}")
    
    try:
        try:
            from .diag import model
        except ImportError:
            from triage.diag import model
            
        diagnosis_data = model.generate_diagnosis(
            session["positive_symptoms"],
            session["negative_symptoms"],
            session["negative_diseases"],
            session["user_age_group"],
            session["expand_search"]
        )
    except Exception as e:
        logger.error(f"Error calling generate_diagnosis: {e}", exc_info=True)
        raise RuntimeError(f'Failed to generate diagnosis: {str(e)}')
    
    if not diagnosis_data:
        logger.warning("generate_diagnosis returned None or empty")
        return {
            'error': 'Failed to generate diagnosis - no data returned',
            'diagnoses': [],
            'questions': [],
            'confidence_reached': False,
            'top_confidence': 0
        }
    
    diagnoses_list = diagnosis_data.get("diagnoses", [])
    if not diagnoses_list or len(diagnoses_list) == 0:
        # Try to provide helpful feedback
        if not session["positive_symptoms"]:
            error_msg = "No symptoms provided. Please extract symptoms first."
        else:
            error_msg = f"No diagnoses found for symptoms: {', '.join(session['positive_symptoms'][:5])}. The LLM may need more information."
        
        return {
            'error': error_msg,
            'diagnoses': [],
            'questions': [],
            'confidence_reached': False,
            'top_confidence': 0,
            'suggestions': 'Try providing more specific symptoms or answering follow-up questions.'
        }
    
    # Adjust confidence scores
    for diagnosis in diagnosis_data["diagnoses"]:
        name = diagnosis["name"]
        prev_conf = session["previous_conf"].get(name, diagnosis["confidence"])
        
        num_present = sum(1 for s in session["positive_symptoms"] 
                        if wrap_normalize_symptom(s) in [wrap_normalize_symptom(cs) 
                        for cs in diagnosis.get("canonical_symptoms", [])])
        num_absent = sum(1 for s in session["negative_symptoms"] 
                        if wrap_normalize_symptom(s) in [wrap_normalize_symptom(cs) 
                        for cs in diagnosis.get("canonical_symptoms", [])])
        
        age_relevance = diagnosis.get("age_relevance", "medium")
        age_bonus = {"high": 0.03, "medium": 0.0, "low": -0.02}.get(age_relevance, 0.0)
        
        expected_symptoms = len(diagnosis.get("canonical_symptoms", []))
        coverage_bonus = 0.0
        if expected_symptoms > 0:
            coverage_ratio = num_present / expected_symptoms
            if coverage_ratio >= 0.9:
                coverage_bonus = 0.12
            elif coverage_ratio >= 0.75:
                coverage_bonus = 0.07
            elif coverage_ratio >= 0.6:
                coverage_bonus = 0.03
        
        diagnosis["confidence"] = max(0, min(1,
            prev_conf - 0.03 * num_absent + age_bonus + coverage_bonus
        ))
        session["previous_conf"][name] = diagnosis["confidence"]
    
    # Sort diagnoses
    diagnosis_data["diagnoses"].sort(key=lambda x: x["confidence"], reverse=True)
    
    # Check if confidence threshold reached
    top_conf = max(d["confidence"] for d in diagnosis_data["diagnoses"]) if diagnosis_data["diagnoses"] else 0
    confidence_threshold = 0.95  # Match the threshold in model.py
    
    questions = []
    if top_conf < confidence_threshold and turn < 10:
        # Generate questions
        top_diagnoses = diagnosis_data["diagnoses"][:5]
        
        # Lazy import model for questions
        try:
            from .diag import model
        except ImportError:
            from triage.diag import model

        if session["user_age_group"] and turn < 2:
            age_questions = model.generate_age_specific_questions(
                top_diagnoses, session["user_age_group"], session["asked_symptoms"]
            )
            questions.extend(age_questions)
        
        if len(questions) < 3:
            symptom_questions = model.generate_missing_symptom_questions(
                top_diagnoses, session["asked_symptoms"], session["user_age_group"], max_questions=3
            )
            questions.extend(symptom_questions)
        
        if not questions:
            questions = model.generate_general_medical_questions(
                session["positive_symptoms"], session["asked_symptoms"], max_questions=3
            )
            session["expand_search"] = True
    
    # If confidence threshold reached, return only the top diagnosis
    if top_conf >= confidence_threshold:
        top_diagnosis = diagnosis_data["diagnoses"][0]
        logger.info(f"Confidence threshold reached! Top diagnosis: {top_diagnosis['name']}")
        return {
            "diagnoses": [top_diagnosis],
            "questions": [],
            "confidence_reached": True,
            "top_confidence": top_conf,
            "turn": turn + 1,
            "top_diagnosis": top_diagnosis
        }
    
    session["turn"] += 1
    
    return {
        "diagnoses": diagnosis_data["diagnoses"],
        "questions": questions,
        "confidence_reached": False,
        "top_confidence": top_conf,
        "turn": turn + 1
    }

def answer_question_logic(session_id: str, question: str, answer: str):
    if not session_id or session_id not in diagnostic_sessions:
        raise ValueError('Invalid session_id')
    
    session = diagnostic_sessions[session_id]
    
    # Step 1: Extract symptoms from the answer using NER model
    extracted_symptoms = []
    extractor = get_symptom_extractor()
    
    if answer and answer.lower() not in ['yes', 'y', 'no', 'n', 'sometimes', 'occasionally']:
        # Free-text answer - extract symptoms using NER
        if extractor:
            extraction_result = extractor.extract(answer)
            extracted_symptoms = extraction_result.get('symptoms', [])
    
    # Step 2: Process answer based on type
    answer_lower = answer.lower().strip()
    
    if answer_lower in ['yes', 'y']:
        # Yes answer - extract symptom from question
        symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
        if extractor:
            extraction_result = extractor.extract(symptom_text)
            if extraction_result.get('symptoms'):
                canonical = extraction_result['symptoms'][0]['canonical']
                session["positive_symptoms"].append(canonical)
                session["asked_symptoms"].add(wrap_normalize_symptom(canonical))
            else:
                session["positive_symptoms"].append(wrap_normalize_symptom(symptom_text))
                session["asked_symptoms"].add(wrap_normalize_symptom(symptom_text))
        else:
            session["positive_symptoms"].append(wrap_normalize_symptom(symptom_text))
            session["asked_symptoms"].add(wrap_normalize_symptom(symptom_text))
    
    elif answer_lower in ['no', 'n']:
        # No answer - extract symptom from question as negative
        symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
        if extractor:
            extraction_result = extractor.extract(symptom_text)
            if extraction_result.get('symptoms'):
                canonical = extraction_result['symptoms'][0]['canonical']
                session["negative_symptoms"].append(canonical)
                session["asked_symptoms"].add(wrap_normalize_symptom(canonical))
            else:
                session["negative_symptoms"].append(wrap_normalize_symptom(symptom_text))
                session["asked_symptoms"].add(wrap_normalize_symptom(symptom_text))
        else:
            session["negative_symptoms"].append(wrap_normalize_symptom(symptom_text))
            session["asked_symptoms"].add(wrap_normalize_symptom(symptom_text))
    
    elif answer_lower in ['sometimes', 'occasionally']:
        # Sometimes answer
        symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
        if extractor:
            extraction_result = extractor.extract(symptom_text)
            if extraction_result.get('symptoms'):
                canonical = extraction_result['symptoms'][0]['canonical']
                session["positive_symptoms"].append(canonical)
                session["asked_symptoms"].add(wrap_normalize_symptom(canonical))
            else:
                session["positive_symptoms"].append(wrap_normalize_symptom(symptom_text))
                session["asked_symptoms"].add(wrap_normalize_symptom(symptom_text))
        else:
            session["positive_symptoms"].append(wrap_normalize_symptom(symptom_text))
            session["asked_symptoms"].add(wrap_normalize_symptom(symptom_text))
    
    else:
        # Free-text answer
        if extracted_symptoms:
            for symptom in extracted_symptoms:
                canonical = symptom.get('canonical', symptom.get('text', ''))
                if canonical:
                    session["positive_symptoms"].append(canonical)
                    session["asked_symptoms"].add(wrap_normalize_symptom(canonical))
        else:
            # Fallback: add the answer as-is
            session["positive_symptoms"].append(answer)
            session["asked_symptoms"].add(wrap_normalize_symptom(answer))
    
    return {
        "message": "Answer recorded and symptoms extracted",
        "extracted_symptoms": [s.get('canonical', s.get('text', '')) for s in extracted_symptoms] if extracted_symptoms else [],
        "symptoms": {
            "positive": session["positive_symptoms"],
            "negative": session["negative_symptoms"]
        }
    }

def find_healthcare_logic(illness: str, severity: str, confidence: float, latitude: Optional[float], longitude: Optional[float], location_str: str):
    # Determine severity if not provided
    illness_lower = illness.lower()
    
    # For common viral illnesses, default to mild unless explicitly severe
    common_viral_conditions = ['flu', 'influenza', 'cold', 'viral infection', 'common cold']
    is_common_viral = any(term in illness_lower for term in common_viral_conditions)
    
    if not severity:
        # For common viral illnesses, be conservative with severity
        if is_common_viral:
            if confidence >= 0.95:
                severity = "moderate"  # Even high confidence flu is usually moderate
            else:
                severity = "mild"  # Most flu cases are mild
        else:
            # For other conditions, use confidence-based severity
            if confidence >= 0.9:
                severity = "severe"
            elif confidence >= 0.7:
                severity = "moderate"
            else:
                severity = "mild"
    else:
        # If severity is provided but it's a common viral illness, cap it at moderate
        if is_common_viral and severity.lower() == "severe":
            # Only keep as severe if confidence is very high (might be complications)
            if confidence < 0.95:
                severity = "moderate"
    
    recommendation = get_healthcare_recommendation(illness, severity)
    service_type = recommendation["service_type"]
    
    if service_type == "STAY_HOME":
        return {
            **recommendation,
            "message": "You can stay home and rest.",
            "places": []
        }
    
    # Get coordinates
    lat, lon = None, None
    if latitude is not None and longitude is not None:
        lat, lon = float(latitude), float(longitude)
    elif location_str:
        lat, lon = geocode_location(location_str)
    
    if not lat or not lon:
        return {
            **recommendation,
            "message": "Location not provided.",
            "places": []
        }
    
    nearby_places = find_nearby_places(lat, lon, service_type)
    
    return {
        **recommendation,
        "latitude": lat,
        "longitude": lon,
        "places": nearby_places,
        "message": f"Found {len(nearby_places)} nearby {service_type} facilities."
    }
