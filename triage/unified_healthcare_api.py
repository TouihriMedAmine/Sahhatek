"""
Unified Healthcare API Server
Integrates: Symptom Extraction + Diagnosis + Location Services
"""

# CONFIG
HOST = "localhost"
PORT = 5000
API_KEY = "sk-181c41d701ea417b90694f49adebd97d"
BASE_URL = "https://tokenfactory.esprit.tn/api"

import json
import re
import sys
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

# Initialize logging early (before imports that might fail)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import httpx
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "diag"))

# Import symptom extractor
try:
    from src.extractor import SymptomExtractor
except ImportError:
    from extractor import SymptomExtractor

# Import diagnostic functions
# Need to handle relative imports in diag/model.py
import importlib.util
import os

diag_path = Path(__file__).parent / "diag"

# Import retrival module first
try:
    retrival_spec = importlib.util.spec_from_file_location("retrival", str(diag_path / "retrival.py"))
    retrival = importlib.util.module_from_spec(retrival_spec)
    retrival_spec.loader.exec_module(retrival)
    retrieve_conditions_faiss = retrival.retrieve_conditions_faiss
except Exception as e:
    logger.warning(f"Could not import retrival: {e}")
    retrieve_conditions_faiss = None

# Import model module (it imports retrival, so we need to add it to sys.modules)
try:
    import sys
    sys.modules['retrival'] = retrival  # Make retrival available for model.py
    
    model_spec = importlib.util.spec_from_file_location("model", str(diag_path / "model.py"))
    model = importlib.util.module_from_spec(model_spec)
    
    # Change directory temporarily to handle any file paths in model.py
    old_cwd = os.getcwd()
    os.chdir(diag_path)
    try:
        model_spec.loader.exec_module(model)
    finally:
        os.chdir(old_cwd)
    
    normalize_symptom = model.normalize_symptom
    normalize_answer = model.normalize_answer
    determine_age_group = model.determine_age_group
    generate_diagnosis = model.generate_diagnosis
    generate_missing_symptom_questions = model.generate_missing_symptom_questions
    generate_age_specific_questions = model.generate_age_specific_questions
    generate_general_medical_questions = model.generate_general_medical_questions
    get_all_canonical_symptoms = model.get_all_canonical_symptoms
    retrieve_conditions_expanded = model.retrieve_conditions_expanded
except Exception as e:
    # Logger might not be initialized yet, use print as fallback
    try:
        logger.warning(f"Could not import diagnostic functions: {e}")
    except:
        print(f"WARNING: Could not import diagnostic functions: {e}")
    # Define fallback functions
    def normalize_symptom(s): return s.lower().strip()
    def normalize_answer(q, a): return a.lower()
    def determine_age_group(age): return "adult"
    def generate_diagnosis(*args, **kwargs): return {"diagnoses": []}
    def generate_missing_symptom_questions(*args, **kwargs): return []
    def generate_age_specific_questions(*args, **kwargs): return []
    def generate_general_medical_questions(*args, **kwargs): return []
    def get_all_canonical_symptoms(*args, **kwargs): return set()
    def retrieve_conditions_expanded(*args, **kwargs): return []

app = Flask(__name__)
CORS(app)

# Initialize clients
http_client = httpx.Client(verify=False)
client = OpenAI(api_key=API_KEY, base_url=BASE_URL, http_client=http_client)
geolocator = Nominatim(user_agent="unified_healthcare")

# Initialize symptom extractor
symptom_extractor = None
try:
    logger.info("🔧 Initializing SymptomExtractor (NER model)...")
    # Use absolute paths to ensure model is found
    project_root = Path(__file__).parent
    model_path = project_root / "models" / "symptom_ner_spacy"
    symptom_dict_path = project_root / "data" / "symptom_dict.json"
    
    logger.info(f"   Model path: {model_path}")
    logger.info(f"   Model exists: {model_path.exists()}")
    logger.info(f"   Dict path: {symptom_dict_path}")
    logger.info(f"   Dict exists: {symptom_dict_path.exists()}")
    
    symptom_extractor = SymptomExtractor(
        model_path=str(model_path),
        symptom_dict_path=str(symptom_dict_path)
    )
    logger.info("✅ Symptom extractor initialized successfully")
    
    # Test extraction to verify it works
    test_result = symptom_extractor.extract("I have a headache and fever")
    test_symptoms = test_result.get('symptoms', [])
    logger.info(f"🧪 Test extraction: Found {len(test_symptoms)} symptoms from test text")
    if test_symptoms:
        logger.info(f"   Test symptoms: {[s.get('canonical', '') for s in test_symptoms]}")
    else:
        logger.warning("⚠️ Test extraction returned no symptoms - model may not be working correctly")
except Exception as e:
    logger.error(f"❌ Could not initialize symptom extractor: {e}", exc_info=True)
    symptom_extractor = None

# Global state for diagnostic sessions
diagnostic_sessions: Dict[str, Dict] = {}


def extract_json(text: str) -> str:
    """Safely extract JSON from LLM output"""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return "{}"


def geocode_location(location_str: str) -> tuple:
    """Convert address to latitude/longitude"""
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
    """Get healthcare service recommendation using LLM"""
    system_message = """You are a medical triage assistant. Recommend the most appropriate healthcare service.

Respond with ONLY: SERVICE_TYPE|IMMEDIATE_CARE

SERVICE_TYPE ∈ {PHARMACY, DOCTOR, HOSPITAL, MENTAL_HEALTH, CLINIC, URGENT_CARE, STAY_HOME}
IMMEDIATE_CARE ∈ {YES, NO}

Rules:
1. Serious/life-threatening conditions → HOSPITAL|YES
2. Mental health issues → MENTAL_HEALTH|YES/NO
3. Minor conditions → STAY_HOME|NO or PHARMACY|NO
4. Moderate issues → DOCTOR|NO or CLINIC|NO
5. Urgent but not emergency → URGENT_CARE|YES/NO"""
    
    user_message = f"Illness: {illness}\nSeverity: {severity if severity else 'Not specified'}\n\nRespond with ONLY:\nSERVICE_TYPE|IMMEDIATE_CARE"
    
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
            service_type = "DOCTOR"
            immediate_care = False
        
        return {
            "service_type": service_type,
            "immediate_care": immediate_care,
            "recommendation_text": recommendation_text
        }
    except Exception as e:
        logger.error(f"Error getting healthcare recommendation: {e}")
        return {"service_type": "DOCTOR", "immediate_care": False}


@app.route('/api/extract-symptoms', methods=['POST'])
def extract_symptoms():
    """Extract symptoms from free-text using NER"""
    try:
        data = request.json
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        if not symptom_extractor:
            logger.error("Symptom extractor not initialized!")
            return jsonify({'error': 'Symptom extractor not available'}), 500
        
        logger.info(f"🔍 Extracting symptoms from text: '{text[:100]}...'")
        result = symptom_extractor.extract(text)
        
        symptoms = result.get('symptoms', [])
        logger.info(f"✅ Extracted {len(symptoms)} symptoms: {[s.get('canonical', s.get('text', '')) for s in symptoms]}")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error extracting symptoms: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/start-diagnosis', methods=['POST'])
def start_diagnosis():
    """Start a new diagnostic session or update existing one"""
    try:
        data = request.json
        symptoms_text = data.get('symptoms', '')
        age_input = data.get('age', '')
        session_id = data.get('session_id')
        
        # Create new session if no session_id provided
        if not session_id or session_id not in diagnostic_sessions:
            session_id = f"session_{len(diagnostic_sessions)}_{int(time.time())}"
        
        # Extract symptoms if text provided
        positive_symptoms = []
        if symptoms_text:
            if symptom_extractor:
                logger.info(f"🔍 Using NER model to extract symptoms from: '{symptoms_text[:100]}...'")
                extraction_result = symptom_extractor.extract(symptoms_text)
                extracted = extraction_result.get('symptoms', [])
                positive_symptoms = [s['canonical'] for s in extracted if s.get('canonical')]
                logger.info(f"✅ NER extracted {len(positive_symptoms)} canonical symptoms: {positive_symptoms}")
            else:
                logger.warning("⚠️ Symptom extractor not available, using fallback text splitting")
                # Fallback: simple split
                positive_symptoms = [normalize_symptom(s) for s in re.split(r",|\n", symptoms_text) if s.strip()]
                logger.info(f"Fallback extracted {len(positive_symptoms)} symptoms: {positive_symptoms}")
        
        # Determine age group
        user_age_group = determine_age_group(age_input) if age_input else None
        
        # Initialize or update session
        session_exists = session_id in diagnostic_sessions
        
        if session_exists:
            # Update existing session
            session = diagnostic_sessions[session_id]
            if positive_symptoms:
                # Add new symptoms
                for symptom in positive_symptoms:
                    normalized = normalize_symptom(symptom)
                    if normalized not in [normalize_symptom(s) for s in session["positive_symptoms"]]:
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
                "asked_symptoms": set([normalize_symptom(s) for s in positive_symptoms]),
                "user_age_group": user_age_group,
                "turn": 0,
                "previous_conf": {},
                "expand_search": False
            }
        
        return jsonify({
            "session_id": session_id,
            "age_group": user_age_group or diagnostic_sessions[session_id].get("user_age_group"),
            "symptoms": diagnostic_sessions[session_id]["positive_symptoms"],
            "message": "Session updated" if session_exists else "Diagnostic session started"
        })
    
    except Exception as e:
        logger.error(f"Error starting diagnosis: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/diagnose', methods=['POST'])
def diagnose():
    """Perform one diagnostic turn"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id or session_id not in diagnostic_sessions:
            return jsonify({'error': 'Invalid session_id'}), 400
        
        session = diagnostic_sessions[session_id]
        turn = session["turn"]
        
        # Generate diagnosis
        logger.info(f"Generating diagnosis for session {session_id}, turn {turn}")
        logger.info(f"Positive symptoms: {session['positive_symptoms']}")
        logger.info(f"Negative symptoms: {session['negative_symptoms']}")
        
        try:
            diagnosis_data = generate_diagnosis(
                session["positive_symptoms"],
                session["negative_symptoms"],
                session["negative_diseases"],
                session["user_age_group"],
                session["expand_search"]
            )
        except Exception as e:
            logger.error(f"Error calling generate_diagnosis: {e}", exc_info=True)
            return jsonify({'error': f'Failed to generate diagnosis: {str(e)}'}), 500
        
        if not diagnosis_data:
            logger.warning("generate_diagnosis returned None or empty")
            return jsonify({
                'error': 'Failed to generate diagnosis - no data returned',
                'diagnoses': [],
                'questions': [],
                'confidence_reached': False,
                'top_confidence': 0
            }), 200
        
        diagnoses_list = diagnosis_data.get("diagnoses", [])
        if not diagnoses_list or len(diagnoses_list) == 0:
            logger.warning(f"diagnosis_data has no diagnoses. Data: {diagnosis_data}")
            # Try to provide helpful feedback
            if not session["positive_symptoms"]:
                error_msg = "No symptoms provided. Please extract symptoms first."
            else:
                error_msg = f"No diagnoses found for symptoms: {', '.join(session['positive_symptoms'][:5])}. The LLM may need more information or the symptoms may be too vague."
            
            return jsonify({
                'error': error_msg,
                'diagnoses': [],
                'questions': [],
                'confidence_reached': False,
                'top_confidence': 0,
                'suggestions': 'Try providing more specific symptoms or answering follow-up questions.'
            }), 200
        
        # Adjust confidence scores
        for diagnosis in diagnosis_data["diagnoses"]:
            name = diagnosis["name"]
            prev_conf = session["previous_conf"].get(name, diagnosis["confidence"])
            
            num_present = sum(1 for s in session["positive_symptoms"] 
                            if normalize_symptom(s) in [normalize_symptom(cs) 
                            for cs in diagnosis.get("canonical_symptoms", [])])
            num_absent = sum(1 for s in session["negative_symptoms"] 
                           if normalize_symptom(s) in [normalize_symptom(cs) 
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
            
            if session["user_age_group"] and turn < 2:
                age_questions = generate_age_specific_questions(
                    top_diagnoses, session["user_age_group"], session["asked_symptoms"]
                )
                questions.extend(age_questions)
            
            if len(questions) < 3:
                symptom_questions = generate_missing_symptom_questions(
                    top_diagnoses, session["asked_symptoms"], session["user_age_group"], max_questions=3
                )
                questions.extend(symptom_questions)
            
            if not questions:
                questions = generate_general_medical_questions(
                    session["positive_symptoms"], session["asked_symptoms"], max_questions=3
                )
                session["expand_search"] = True
        
        # If confidence threshold reached, return only the top diagnosis
        if top_conf >= confidence_threshold:
            top_diagnosis = diagnosis_data["diagnoses"][0]
            logger.info(f"Confidence threshold reached! Top diagnosis: {top_diagnosis['name']} (confidence: {top_conf:.2f})")
            return jsonify({
                "diagnoses": [top_diagnosis],  # Return only the highest confidence diagnosis
                "questions": [],
                "confidence_reached": True,
                "top_confidence": top_conf,
                "turn": turn + 1,
                "top_diagnosis": top_diagnosis  # Also include for easy access
            })
        
        session["turn"] += 1
        
        logger.info(f"Diagnosis complete - {len(diagnosis_data['diagnoses'])} diagnoses, top confidence: {top_conf:.2f}, questions: {len(questions)}")
        
        return jsonify({
            "diagnoses": diagnosis_data["diagnoses"],
            "questions": questions,
            "confidence_reached": False,
            "top_confidence": top_conf,
            "turn": turn + 1
        })
    
    except Exception as e:
        logger.error(f"Error in diagnosis: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/answer-question', methods=['POST'])
def answer_question():
    """Answer a diagnostic question - extracts symptoms from answer using NER"""
    try:
        data = request.json
        session_id = data.get('session_id')
        question = data.get('question', '')
        answer = data.get('answer', '')
        
        if not session_id or session_id not in diagnostic_sessions:
            return jsonify({'error': 'Invalid session_id'}), 400
        
        session = diagnostic_sessions[session_id]
        
        # Step 1: Extract symptoms from the answer using NER model
        extracted_symptoms = []
        if answer and answer.lower() not in ['yes', 'y', 'no', 'n', 'sometimes', 'occasionally']:
            # Free-text answer - extract symptoms using NER
            if symptom_extractor:
                extraction_result = symptom_extractor.extract(answer)
                extracted_symptoms = extraction_result.get('symptoms', [])
                logger.info(f"Extracted {len(extracted_symptoms)} symptoms from answer: '{answer}'")
        
        # Step 2: Process answer based on type
        answer_lower = answer.lower().strip()
        
        if answer_lower in ['yes', 'y']:
            # Yes answer - extract symptom from question
            symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
            if symptom_extractor:
                # Try to extract and normalize the symptom from question
                extraction_result = symptom_extractor.extract(symptom_text)
                if extraction_result.get('symptoms'):
                    canonical = extraction_result['symptoms'][0]['canonical']
                    session["positive_symptoms"].append(canonical)
                    session["asked_symptoms"].add(normalize_symptom(canonical))
                else:
                    session["positive_symptoms"].append(normalize_symptom(symptom_text))
                    session["asked_symptoms"].add(normalize_symptom(symptom_text))
            else:
                session["positive_symptoms"].append(normalize_symptom(symptom_text))
                session["asked_symptoms"].add(normalize_symptom(symptom_text))
        
        elif answer_lower in ['no', 'n']:
            # No answer - extract symptom from question as negative
            symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
            if symptom_extractor:
                extraction_result = symptom_extractor.extract(symptom_text)
                if extraction_result.get('symptoms'):
                    canonical = extraction_result['symptoms'][0]['canonical']
                    session["negative_symptoms"].append(canonical)
                    session["asked_symptoms"].add(normalize_symptom(canonical))
                else:
                    session["negative_symptoms"].append(normalize_symptom(symptom_text))
                    session["asked_symptoms"].add(normalize_symptom(symptom_text))
            else:
                session["negative_symptoms"].append(normalize_symptom(symptom_text))
                session["asked_symptoms"].add(normalize_symptom(symptom_text))
        
        elif answer_lower in ['sometimes', 'occasionally']:
            # Sometimes answer - treat as positive but intermittent
            symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
            if symptom_extractor:
                extraction_result = symptom_extractor.extract(symptom_text)
                if extraction_result.get('symptoms'):
                    canonical = extraction_result['symptoms'][0]['canonical']
                    session["positive_symptoms"].append(canonical)
                    session["asked_symptoms"].add(normalize_symptom(canonical))
                else:
                    session["positive_symptoms"].append(normalize_symptom(symptom_text))
                    session["asked_symptoms"].add(normalize_symptom(symptom_text))
            else:
                session["positive_symptoms"].append(normalize_symptom(symptom_text))
                session["asked_symptoms"].add(normalize_symptom(symptom_text))
        
        else:
            # Free-text answer - use extracted symptoms from NER
            if extracted_symptoms:
                for symptom in extracted_symptoms:
                    canonical = symptom.get('canonical', symptom.get('text', ''))
                    if canonical:
                        session["positive_symptoms"].append(canonical)
                        session["asked_symptoms"].add(normalize_symptom(canonical))
            else:
                # Fallback: add the answer as-is
                session["positive_symptoms"].append(answer)
                session["asked_symptoms"].add(normalize_symptom(answer))
        
        return jsonify({
            "message": "Answer recorded and symptoms extracted",
            "extracted_symptoms": [s.get('canonical', s.get('text', '')) for s in extracted_symptoms] if extracted_symptoms else [],
            "symptoms": {
                "positive": session["positive_symptoms"],
                "negative": session["negative_symptoms"]
            }
        })
    
    except Exception as e:
        logger.error(f"Error answering question: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/find-healthcare', methods=['POST'])
def find_healthcare():
    """Find nearby healthcare facilities based on diagnosis (triage model)"""
    try:
        data = request.json
        illness = data.get('illness', '')
        severity = data.get('severity', '')
        confidence = data.get('confidence', 0.5)  # Diagnosis confidence
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        location_str = data.get('location', '')
        
        # Determine severity based on confidence if not provided
        if not severity:
            if confidence >= 0.9:
                severity = "severe"
            elif confidence >= 0.7:
                severity = "moderate"
            else:
                severity = "mild"
        
        # Get recommendation from triage model
        recommendation = get_healthcare_recommendation(illness, severity)
        service_type = recommendation["service_type"]
        
        if service_type == "STAY_HOME":
            return jsonify({
                **recommendation,
                "message": "You can stay home and rest. No medical facility visit needed.",
                "places": []
            })
        
        # Get coordinates
        lat, lon = None, None
        if latitude is not None and longitude is not None:
            lat, lon = float(latitude), float(longitude)
        elif location_str:
            lat, lon = geocode_location(location_str)
        
        if not lat or not lon:
            return jsonify({
                **recommendation,
                "message": "Location not provided. Please provide your location.",
                "places": []
            })
        
        # Find nearby places
        nearby_places = find_nearby_places(lat, lon, service_type)
        
        return jsonify({
            **recommendation,
            "latitude": lat,
            "longitude": lon,
            "places": nearby_places,
            "message": f"Found {len(nearby_places)} nearby {service_type} facilities."
        })
    
    except Exception as e:
        logger.error(f"Error finding healthcare: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'symptom_extractor': symptom_extractor is not None,
        'sessions': len(diagnostic_sessions)
    })


if __name__ == '__main__':
    logger.info(f"Starting Unified Healthcare API on http://{HOST}:{PORT}")
    logger.info(f"API endpoints:")
    logger.info(f"  - POST /api/extract-symptoms")
    logger.info(f"  - POST /api/start-diagnosis")
    logger.info(f"  - POST /api/diagnose")
    logger.info(f"  - POST /api/answer-question")
    logger.info(f"  - POST /api/find-healthcare")
    logger.info(f"  - GET /health")
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)

