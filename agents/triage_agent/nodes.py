# agents/triage_agent/nodes.py
"""
Separate LangGraph nodes for triage workflow:
1. Extraction node - Extract symptoms from user input
2. Diagnosis node - Identify disease (placeholder)
3. Triage node - Determine facility type from disease and severity
4. Orientation node - Find nearest facility
"""

from __future__ import annotations
import os
import sys
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import httpx

logger = logging.getLogger(__name__)

# Import from existing triage agent
from .agent import (
    get_http_client,
    get_geolocator,
    get_llm_client,
    normalize_symptom,
    get_knowledge_base,
    get_healthcare_recommendation,
    find_nearby_facilities,
    geocode_location
)

# ============================================================
# 1. EXTRACTION NODE
# ============================================================
def extraction_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract symptoms from user input using LLM.
    Returns: symptoms (list), negative_symptoms (list)
    """
    logger.info("🔍 EXTRACTION NODE: Extracting symptoms from user input using LLM")
    
    try:
        user_input = state.get("user_input", "")
        if not user_input:
            return {
                "symptoms": [],
                "negative_symptoms": [],
                "current_agent": "extraction",
                "agent_output": "Please provide symptom information"
            }
        
        logger.info(f"🔍 Extracting symptoms from: '{user_input[:100]}'")
        
        # Use LLM to extract symptoms
        llm_client = get_llm_client()
        if not llm_client:
            logger.warning("⚠️ LLM client not available, using fallback")
            # Fallback: simple parsing
            symptoms = [s.strip() for s in user_input.split(",") if s.strip()]
            return {
                "symptoms": symptoms,
                "negative_symptoms": [],
                "current_agent": "extraction",
                "agent_output": f"Detected symptoms: {', '.join(symptoms)}"
            }
        
        # Get model name based on client type
        model_name = "meta-llama/llama-3.1-8b-instruct"
        if hasattr(llm_client, 'model'):  # Groq client
            model_name = "meta-llama/llama-3.1-8b-instruct"
        else:  # OpenAI client
            model_name = "hosted_vllm/Llama-3.1-70B-Instruct"
        
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
                # Fallback for other client types
                logger.warning("Unknown LLM client type, using fallback")
                symptoms = [s.strip() for s in user_input.split(",") if s.strip()]
                return {
                    "symptoms": symptoms,
                    "negative_symptoms": [],
                    "current_agent": "extraction",
                    "agent_output": f"Detected symptoms: {', '.join(symptoms)}"
                }
            
            # Parse JSON response
            import json
            import re
            
            # Extract JSON from response (handle cases where LLM adds extra text)
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                positive_symptoms = result.get("positive_symptoms", [])
                negative_symptoms = result.get("negative_symptoms", [])
                
                # Normalize symptoms using normalize_symptom if available
                if normalize_symptom:
                    positive_symptoms = [normalize_symptom(s) for s in positive_symptoms if s]
                    negative_symptoms = [normalize_symptom(s) for s in negative_symptoms if s]
                else:
                    # Simple normalization
                    positive_symptoms = [s.lower().strip().replace(" ", "_") for s in positive_symptoms if s]
                    negative_symptoms = [s.lower().strip().replace(" ", "_") for s in negative_symptoms if s]
                
                logger.info(f"✅ Extracted {len(positive_symptoms)} positive and {len(negative_symptoms)} negative symptoms")
                
                return {
                    "symptoms": positive_symptoms,
                    "negative_symptoms": negative_symptoms,
                    "extraction_result": {"method": "llm", "raw_response": content},
                    "current_agent": "extraction",
                    "agent_output": f"Extracted {len(positive_symptoms)} positive and {len(negative_symptoms)} negative symptoms"
                }
            else:
                logger.warning(f"⚠️ Could not parse JSON from LLM response: {content[:200]}")
                # Fallback
                symptoms = [s.strip() for s in user_input.split(",") if s.strip()]
                return {
                    "symptoms": symptoms,
                    "negative_symptoms": [],
                    "current_agent": "extraction",
                    "agent_output": f"Detected symptoms: {', '.join(symptoms)}"
                }
                
        except Exception as e:
            logger.error(f"Error calling LLM for symptom extraction: {e}", exc_info=True)
            # Fallback: simple parsing
            symptoms = [s.strip() for s in user_input.split(",") if s.strip()]
            return {
                "symptoms": symptoms,
                "negative_symptoms": [],
                "current_agent": "extraction",
                "agent_output": f"Detected symptoms: {', '.join(symptoms)}"
            }
            
    except Exception as e:
        logger.error(f"Error in extraction node: {e}", exc_info=True)
        return {
            "symptoms": [],
            "negative_symptoms": [],
            "current_agent": "extraction",
            "agent_output": f"Error extracting symptoms: {str(e)}"
        }


# ============================================================
# DIAGNOSIS SESSION MANAGEMENT
# ============================================================
# Global diagnostic sessions storage
_diagnosis_sessions: Dict[str, Dict] = {}

CONFIDENCE_THRESHOLD = 0.97
MAX_DIAGNOSIS_TURNS = 10

# ============================================================
# 2. DIAGNOSIS NODE (Multi-turn Q&A)
# ============================================================
def diagnosis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Multi-turn Q&A diagnosis node that asks questions until confidence threshold is reached.
    
    Flow:
    1. Check for pending_questions (answer from previous turn)
    2. If yes, process answer and update symptoms
    3. Generate/update diagnoses
    4. Check confidence threshold (0.97)
    5. If < threshold: generate questions, set pending_questions, loop back
    6. If >= threshold: return diagnosis and proceed to triage
    """
    logger.info("🩺 DIAGNOSIS NODE: Multi-turn Q&A")
    
    try:
        import json
        import re
        import uuid
        
        # Import diagnosis helpers
        from .diagnosis_logic import (
            get_diagnosis_helpers,
            calculate_diagnosis_confidence,
            generate_questions_from_diagnoses,
            process_answer
        )
        
        helpers = get_diagnosis_helpers()
        normalize_symptom_func = helpers["normalize_symptom"]
        determine_age_group_func = helpers["determine_age_group"]
        retrieve_conditions_faiss = helpers["retrieve_conditions_faiss"]
        
        # Get state
        symptoms = state.get("symptoms", [])
        negative_symptoms = state.get("negative_symptoms", [])
        user_input = state.get("user_input", "").strip()
        pending_questions = state.get("pending_questions", [])
        diagnosis_session_id = state.get("diagnosis_session_id")
        messages = state.get("messages", [])
        
        # Check if this is an answer to a pending question
        # Only consider it an answer if:
        # 1. We have pending questions
        # 2. User provided input
        # 3. Input is short (yes/no/simple answer) OR doesn't contain symptom keywords
        # 4. Input is NOT a new symptom description (like "i have high temperature")
        short_answer_keywords = ['yes', 'no', 'y', 'n', 'yeah', 'yep', 'nope', 'nah', 'sure', 'correct', 'right', 'negative', 'affirmative', 'not']
        symptom_keywords = ['have', 'feel', 'pain', 'ache', 'hurt', 'symptom', 'temperature', 'fever', 'headache', 'cough']
        
        is_short_answer = user_input.lower().strip() in short_answer_keywords
        contains_symptom_keywords = any(keyword in user_input.lower() for keyword in symptom_keywords)
        
        # It's an answer if: short answer OR (has pending questions AND doesn't look like new symptoms)
        is_answer = bool(pending_questions) and bool(user_input) and (
            is_short_answer or (len(user_input) < 50 and not contains_symptom_keywords)
        )
        
        # If user input looks like new symptoms, clear pending_questions and start fresh
        if pending_questions and contains_symptom_keywords and not is_short_answer:
            logger.info(f"🔄 User input '{user_input}' looks like new symptoms, not an answer - clearing pending questions and starting fresh")
            pending_questions = []
            is_answer = False
            # Clear the old session_id since we're starting fresh
            diagnosis_session_id = None
        
        # Get or create diagnosis session
        if not diagnosis_session_id:
            diagnosis_session_id = str(uuid.uuid4())
            _diagnosis_sessions[diagnosis_session_id] = {
                "positive_symptoms": list(symptoms),
                "negative_symptoms": list(negative_symptoms),
                "asked_symptoms": set([normalize_symptom_func(s) for s in symptoms]),
                "turn": 0,
                "diagnoses": []
            }
            logger.info(f"🆕 Created new diagnosis session: {diagnosis_session_id}")
        else:
            # Check if session exists (might have been cleared on server restart)
            if diagnosis_session_id not in _diagnosis_sessions:
                logger.warning(f"⚠️ Session {diagnosis_session_id} not found - hydrating from history / creating new session")

                # If we're answering yes/no, extraction node may have produced empty symptoms.
                # Recover last-known symptoms from assistant metadata (saved in views.py).
                if is_answer and (not symptoms):
                    for msg in reversed(messages):
                        if msg.get("role") == "assistant":
                            msg_meta = msg.get("metadata", {})
                            if isinstance(msg_meta, str):
                                try:
                                    import json as _json
                                    msg_meta = _json.loads(msg_meta)
                                except Exception:
                                    msg_meta = {}
                            if isinstance(msg_meta, dict):
                                recovered = msg_meta.get("symptoms", []) or []
                                recovered_neg = msg_meta.get("negative_symptoms", []) or []
                                if recovered:
                                    symptoms = list(recovered)
                                if recovered_neg:
                                    negative_symptoms = list(recovered_neg)
                                if recovered or recovered_neg:
                                    logger.info(
                                        f"🧠 Recovered symptoms from history: +{len(symptoms)} / -{len(negative_symptoms)}"
                                    )
                                    break

                diagnosis_session_id = str(uuid.uuid4())
                _diagnosis_sessions[diagnosis_session_id] = {
                    "positive_symptoms": list(symptoms),
                    "negative_symptoms": list(negative_symptoms),
                    "asked_symptoms": set([normalize_symptom_func(s) for s in symptoms]),
                    "turn": 0,
                    "diagnoses": []
                }
                logger.info(f"🆕 Created new diagnosis session: {diagnosis_session_id}")
            else:
                session = _diagnosis_sessions[diagnosis_session_id]
                symptoms = list(session.get("positive_symptoms", []))
                negative_symptoms = list(session.get("negative_symptoms", []))
                logger.info(f"📋 Using existing session: {diagnosis_session_id}")
        
        session = _diagnosis_sessions[diagnosis_session_id]
        
        # Process answer if this is a response to a question
        if is_answer and pending_questions:
            # ALWAYS extract question from most recent assistant message content
            # This is more reliable than metadata which might be stale
            question = None
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    # Try to extract question from agent_output content
                    if "Do you have" in content and "?" in content:
                        import re
                        question_match = re.search(r'Do you have [^?]+\?', content)
                        if question_match:
                            question = question_match.group(0)
                            logger.info(f"📋 Extracted question from message content: {question}")
                            break
            
            # Fallback to pending_questions if extraction from content failed
            if not question and pending_questions:
                question = pending_questions[0]
                logger.info(f"📋 Using question from pending_questions: {question}")
            
            if not question:
                logger.warning("⚠️ No question found to process answer")
            else:
                answer = user_input
                logger.info(f"📝 Processing answer '{answer}' to question: {question}")
                
                symptom_normalized, is_positive = process_answer(question, answer, normalize_symptom_func)
                
                if symptom_normalized:
                    if symptom_normalized not in session["asked_symptoms"]:
                        session["asked_symptoms"].add(symptom_normalized)
                    
                    if is_positive:
                        if symptom_normalized not in symptoms:
                            symptoms.append(symptom_normalized)
                            logger.info(f"✅ Added positive symptom: {symptom_normalized}")
                    else:
                        if symptom_normalized not in negative_symptoms:
                            negative_symptoms.append(symptom_normalized)
                            logger.info(f"❌ Added negative symptom: {symptom_normalized}")
                
                # Update session
                session["positive_symptoms"] = symptoms
                session["negative_symptoms"] = negative_symptoms
                session["turn"] += 1

                # IMPORTANT: we have consumed the pending question for this turn.
                # Clear it so the router does NOT loop diagnosis again within the same graph.invoke().
                pending_questions = []
                # Also clear user_input in returned state to avoid router thinking there's still an "answer" to process.
                user_input = ""
        
        if not symptoms:
            return {
                "disease": "unknown",
                "severity": "moderate",
                "confidence": 0.5,
                "current_agent": "diagnosis",
                "agent_output": "No symptoms provided",
                "pending_questions": [],  # Clear pending questions if no symptoms
                "diagnosis_session_id": None  # Clear session if no symptoms
            }
        
        # Determine age group
        user_context = state.get("metadata", {}).get("user_context", {})
        age_input = user_context.get("age") or "adult"
        user_age_group = determine_age_group_func(str(age_input))
        logger.info(f"📊 User age group: {user_age_group}")
        
        # Normalize symptoms
        normalized_symptoms = [normalize_symptom_func(s) for s in symptoms]
        normalized_negative = [normalize_symptom_func(s) for s in negative_symptoms]
        
        # Retrieve conditions
        symptoms_text = " ".join(normalized_symptoms)
        logger.info(f"🔍 Retrieving conditions for symptoms: {symptoms_text}")
        
        conditions = retrieve_conditions_faiss(symptoms_text, top_k=15, user_age_group=user_age_group)
        
        if not conditions:
            logger.warning("⚠️ No conditions retrieved - cannot proceed with diagnosis")
            # If no conditions, we can't ask questions, so proceed with unknown diagnosis
            return {
                "disease": "unknown",
                "severity": "moderate",
                "confidence": 0.5,
                "diagnosis_complete": True,  # Mark as complete so it proceeds to triage
                "current_agent": "diagnosis",
                "agent_output": "No matching conditions found in knowledge base. Please consult a doctor."
            }
        
        logger.info(f"✅ Retrieved {len(conditions)} conditions")
        
        # Prepare for LLM
        conditions_summary = []
        for i, cond in enumerate(conditions[:15]):
            cond_symptoms = cond.get("symptoms", [])
            conditions_summary.append({
                "id": i + 1,
                "name": cond.get("name", "Unknown"),
                "canonical_symptoms": cond_symptoms[:8] if isinstance(cond_symptoms, list) else [],
                "total_symptoms": len(cond_symptoms) if isinstance(cond_symptoms, list) else 0
            })
        
        # Get LLM client
        from .agent import get_llm_client
        client = get_llm_client()
        
        if not client:
            top_condition = conditions[0]
            return {
                "disease": top_condition.get("name", "unknown"),
                "severity": "moderate",
                "confidence": 0.6,
                "current_agent": "diagnosis",
                "agent_output": f"Diagnosed: {top_condition.get('name', 'unknown')}"
            }
        
        # LLM prompt
        prompt = f"""You are a medical diagnosis selector.

PATIENT INFORMATION:
- Age group: {user_age_group}
- Confirmed symptoms: {normalized_symptoms}
- Absent symptoms: {normalized_negative}

CONDITIONS FROM DATABASE:
{json.dumps(conditions_summary, indent=2)}

Select 3-5 most relevant conditions. Return ONLY JSON:

{{
  "selected_conditions": [
    {{
      "name": "EXACT_NAME_FROM_LIST",
      "canonical_symptoms": ["symptom1", "symptom2", ...]
    }}
  ]
}}"""
        
        try:
            # Determine which model to use based on client type
            # Groq uses different model names than OpenAI-compatible APIs
            if hasattr(client, 'models') and 'groq' in str(type(client)).lower():
                # Groq client - use Groq model
                model_name = "llama-3.1-70b-versatile"
            else:
                # OpenAI-compatible client (custom API)
                model_name = "hosted_vllm/Llama-3.1-70B-Instruct"
            
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            
            if not json_match:
                top_condition = conditions[0]
                return {
                    "disease": top_condition.get("name", "unknown"),
                    "severity": "moderate",
                    "confidence": 0.6,
                    "current_agent": "diagnosis",
                    "agent_output": f"Diagnosed: {top_condition.get('name', 'unknown')}"
                }
            
            data = json.loads(json_match.group())
            selected_conditions = data.get("selected_conditions", [])
            
            if not selected_conditions:
                top_condition = conditions[0]
                return {
                    "disease": top_condition.get("name", "unknown"),
                    "severity": "moderate",
                    "confidence": 0.6,
                    "current_agent": "diagnosis",
                    "agent_output": f"Diagnosed: {top_condition.get('name', 'unknown')}"
                }
            
            # Calculate confidence for each
            diagnoses = []
            for condition in selected_conditions[:5]:
                diagnosis = {
                    "name": condition["name"],
                    "canonical_symptoms": condition.get("canonical_symptoms", []),
                    "confidence": 0.5
                }
                
                confidence = calculate_diagnosis_confidence(
                    diagnosis=diagnosis,
                    positive_symptoms=normalized_symptoms,
                    negative_symptoms=normalized_negative,
                    age_group=user_age_group,
                    normalize_symptom_func=normalize_symptom_func
                )
                
                diagnosis["confidence"] = confidence
                diagnoses.append(diagnosis)
            
            diagnoses.sort(key=lambda x: x["confidence"], reverse=True)
            session["diagnoses"] = diagnoses
            
            if not diagnoses:
                return {
                    "disease": "unknown",
                    "severity": "moderate",
                    "confidence": 0.5,
                    "current_agent": "diagnosis",
                    "agent_output": "Could not determine diagnosis"
                }
            
            # Get top diagnosis
            top_diagnosis = diagnoses[0]
            confidence_score = top_diagnosis["confidence"]
            
            # Check confidence threshold
            if confidence_score >= CONFIDENCE_THRESHOLD or session["turn"] >= MAX_DIAGNOSIS_TURNS:
                # Diagnosis complete - proceed to triage
                disease_name = top_diagnosis["name"]
                
                # Map severity
                if confidence_score >= 0.8:
                    severity = "severe"
                elif confidence_score >= 0.6:
                    severity = "moderate"
                else:
                    severity = "mild"
                
                logger.info(f"✅ Diagnosis complete: {disease_name} (confidence: {confidence_score:.2f})")
                
                # Clear session
                if diagnosis_session_id in _diagnosis_sessions:
                    del _diagnosis_sessions[diagnosis_session_id]
                
                return {
                    "disease": disease_name,
                    "severity": severity,
                    "confidence": confidence_score,
                    "confidence_score": confidence_score,
                    "diagnosis_complete": True,
                    "current_agent": "diagnosis",
                    "pending_questions": [],
                    "should_end": False,
                    "user_input": "",
                    "agent_output": f"Diagnosed: {disease_name} (confidence: {confidence_score:.1%})"
                }
            else:
                # Confidence not met - generate questions
                asked_set = session["asked_symptoms"]
                top_3 = diagnoses[:3]
                
                questions = generate_questions_from_diagnoses(
                    top_3,
                    asked_set,
                    normalize_symptom_func
                )
                
                if not questions:
                    # No more questions - proceed with current diagnosis
                    disease_name = top_diagnosis["name"]
                    severity = "moderate" if confidence_score >= 0.6 else "mild"
                    
                    if diagnosis_session_id in _diagnosis_sessions:
                        del _diagnosis_sessions[diagnosis_session_id]
                    
                    return {
                        "disease": disease_name,
                        "severity": severity,
                        "confidence": confidence_score,
                        "confidence_score": confidence_score,
                        "diagnosis_complete": True,
                        "current_agent": "diagnosis",
                        "pending_questions": [],
                        "should_end": False,
                        "user_input": "",
                        "agent_output": f"Diagnosed: {disease_name} (confidence: {confidence_score:.1%})"
                    }
                
                # Return first question
                question = questions[0]
                logger.info(f"❓ Asking question: {question} (confidence: {confidence_score:.2f} < {CONFIDENCE_THRESHOLD})")
                
                return {
                    "symptoms": symptoms,  # Update state with current symptoms
                    "negative_symptoms": negative_symptoms,
                    "diagnosis_session_id": diagnosis_session_id,
                    "pending_questions": [question],  # Only one question at a time
                    "confidence_score": confidence_score,
                    "current_agent": "diagnosis",
                    "should_end": True,  # End graph to wait for user answer
                    "user_input": "",
                    "agent_output": (
                        f"I need to ask you a question to better understand your condition "
                        f"and provide an accurate diagnosis.\n"
                        f"(Current confidence: {confidence_score:.0%}, target: {CONFIDENCE_THRESHOLD:.0%})\n\n"
                        f"{question}"
                    )
                }
                
        except Exception as e:
            logger.error(f"Error in diagnosis: {e}", exc_info=True)
            return {
                "disease": "unknown",
                "severity": "moderate",
                "confidence": 0.5,
                "current_agent": "diagnosis",
                "agent_output": f"Error in diagnosis: {str(e)}"
            }
            
    except Exception as e:
        logger.error(f"Error in diagnosis node: {e}", exc_info=True)
        return {
            "disease": "unknown",
            "severity": "moderate",
            "confidence": 0.5,
            "current_agent": "diagnosis",
            "agent_output": f"Error: {str(e)}"
        }


# ============================================================
# 3. TRIAGE NODE
# ============================================================
def triage_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine facility type from disease and severity.
    Input format: "disease,severity" or separate disease and severity fields
    Returns: service_type (HOSPITAL, PHARMACY, CLINIC, URGENT_CARE, MENTAL_HEALTH, PSYCHIATRIST, STAY_HOME)
    Note: ER maps to HOSPITAL with immediate_care=True
    """
    logger.info("🏥 TRIAGE NODE: Determining facility type")
    
    try:
        # Get disease and severity from state
        disease = state.get("disease", "")
        severity = state.get("severity", "")
        
        # Also check if it's in format "disease,severity"
        if not disease and state.get("user_input"):
            user_input = state.get("user_input", "")
            if "," in user_input:
                parts = user_input.split(",", 1)
                disease = parts[0].strip()
                severity = parts[1].strip() if len(parts) > 1 else ""
        
        # Check for mental health input from mental_health node
        mental_health_input = state.get("mental_health_recommendation", "")
        if mental_health_input:
            if mental_health_input.lower() in ["emergency", "urgent"]:
                return {
                    "service_type": "PSYCHIATRIST",
                    "immediate_care": True,
                    "recommendation_text": "Mental health emergency - seek immediate psychiatric care",
                    "agent_output": "🚨 Mental health emergency detected"
                }
            elif mental_health_input.lower() == "therapist":
                return {
                    "service_type": "PSYCHIATRIST",
                    "immediate_care": False,
                    "recommendation_text": "Schedule appointment with therapist/psychiatrist",
                    "agent_output": "Therapist/psychiatrist recommended"
                }
        
        if not disease:
            logger.warning("⚠️ No disease provided to triage node")
            return {
                "service_type": "DOCTOR",
                "immediate_care": False,
                "recommendation_text": "Consult a doctor for evaluation",
                "agent_output": "No disease specified - defaulting to doctor"
            }
        
        logger.info(f"📋 Triage input: disease='{disease}', severity='{severity}'")
        
        # Use existing triage logic
        recommendation = get_healthcare_recommendation(disease, severity)
        
        service_type = recommendation.get("service_type", "DOCTOR")
        immediate_care = recommendation.get("immediate_care", False)
        
        # Map ER to HOSPITAL with immediate_care=True
        if service_type == "ER" or (service_type == "HOSPITAL" and immediate_care):
            service_type = "HOSPITAL"
            immediate_care = True
        
        logger.info(f"✅ Triage recommendation: {service_type} (immediate_care={immediate_care})")
        
        return {
            "service_type": service_type,
            "immediate_care": immediate_care,
            "recommendation_text": recommendation.get("recommendation_text", ""),
            "current_agent": "triage",
            "agent_output": f"Recommended facility: {service_type}"
        }
    except Exception as e:
        logger.error(f"Error in triage node: {e}", exc_info=True)
        return {
            "service_type": "DOCTOR",
            "immediate_care": False,
            "recommendation_text": "Error in triage - defaulting to doctor",
            "agent_output": f"Triage error: {str(e)}"
        }


# ============================================================
# 4. ORIENTATION NODE
# ============================================================
def orientation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find nearest facility based on triage recommendation.
    Can also handle:
    - Direct facility requests (e.g., "show me nearest pharmacies")
    - Mental health input ("emergency" or "therapist")
    Returns: nearby_facilities (list), selected_facility (dict)
    """
    logger.info("🧭 ORIENTATION NODE: Finding nearest facility")
    
    try:
        service_type = state.get("service_type", "")
        user_location = state.get("user_location")
        user_input_location = state.get("user_input_location", "")
        user_input = state.get("user_input", "").lower()
        
        # IMPORTANT: Detect direct facility requests early
        # e.g., "where is the nearest pharmacy", "find hospitals near me"
        if not service_type:
            facility_keywords = {
                "PHARMACY": ["pharmacy", "pharmacies", "pharmacie", "صيدلية", "صيدليات", "pharma"],
                "HOSPITAL": ["hospital", "hospitals", "مستشفى", "مستشفيات", "hopital"],
                "CLINIC": ["clinic", "clinics", "عيادة", "عيادات", "clinique"],
                "DOCTOR": ["doctor", "doctors", "طبيب", "أطباء", "medecin", "medecins"],
                "URGENT_CARE": ["urgent care", "urgence", "طوارئ", "emergency room", "er", "urgent"]
            }
            
            for facility_type, keywords in facility_keywords.items():
                if any(keyword in user_input for keyword in keywords):
                    service_type = facility_type
                    logger.info(f"📍 DIRECT REQUEST: Detected facility type from user input: {service_type}")
                    state["service_type"] = service_type
                    break
        
        # Handle mental health emergency/therapist
        mental_health_input = state.get("mental_health_recommendation", "")
        if mental_health_input:
            if mental_health_input.lower() in ["emergency", "urgent"]:
                service_type = "PSYCHIATRIST"
                state["immediate_care"] = True
            elif mental_health_input.lower() == "therapist":
                service_type = "PSYCHIATRIST"
                state["immediate_care"] = False
        
        if not service_type:
            logger.warning("⚠️ No service_type provided to orientation node")
            return {
                "nearby_facilities": [],
                "selected_facility": None,
                "current_agent": "orientation",
                "should_end": True,
                "agent_output": "No service type specified. Please specify what type of facility you're looking for (pharmacy, hospital, clinic, etc.)."
            }
        
        # Get user location - prioritize different sources
        lat, lon = None, None
        
        logger.info(f"🔍 Location check - user_location: {user_location}, user_input_location: {user_input_location}")
        
        # 1. Try messages history for geolocation metadata from browser
        messages_history = state.get("messages", [])
        if messages_history and not user_location:
            # Look for latitude/longitude in message metadata
            for msg in reversed(messages_history):  # Most recent first
                if isinstance(msg, dict) and msg.get("metadata"):
                    metadata = msg.get("metadata")
                    if isinstance(metadata, dict):
                        if "latitude" in metadata and "longitude" in metadata:
                            try:
                                lat = float(metadata["latitude"])
                                lon = float(metadata["longitude"])
                                logger.info(f"📍 Found location in message metadata: ({lat}, {lon})")
                                break
                            except (ValueError, TypeError):
                                pass
        
        # 2. Try direct user_location tuple from state (latitude/longitude from request)
        if not lat or not lon:
            if user_location:
                if isinstance(user_location, (list, tuple)) and len(user_location) >= 2:
                    try:
                        lat, lon = float(user_location[0]), float(user_location[1])
                        logger.info(f"📍 Using location from state tuple: ({lat}, {lon})")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"⚠️ Error parsing user_location tuple: {e}")
                elif isinstance(user_location, dict):
                    # Handle dict format like {"latitude": 36.8065, "longitude": 10.1815}
                    if "latitude" in user_location and "longitude" in user_location:
                        try:
                            lat, lon = float(user_location["latitude"]), float(user_location["longitude"])
                            logger.info(f"📍 Using location from state dict: ({lat}, {lon})")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"⚠️ Error parsing user_location dict: {e}")
        
        # 3. Try user_input_location string (geocode it)
        if not lat or not lon:
            if user_input_location:
                lat, lon = geocode_location(user_input_location)
                if lat and lon:
                    logger.info(f"📍 Geocoded location from string '{user_input_location}': ({lat}, {lon})")
        
        # 4. Try to extract from user_input text (fallback)
        if not lat or not lon:
            user_input = state.get("user_input", "")
            if user_input:
                # Check if user mentioned coordinates or location in their message
                import re
                coord_pattern = r'(-?\d+\.?\d*)\s*[,;]\s*(-?\d+\.?\d*)'
                match = re.search(coord_pattern, user_input)
                if match:
                    try:
                        lat, lon = float(match.group(1)), float(match.group(2))
                        if -90 <= lat <= 90 and -180 <= lon <= 180:
                            logger.info(f"📍 Extracted coordinates from user input: ({lat}, {lon})")
                    except:
                        pass
        
        if not lat or not lon:
            logger.warning("⚠️ No location provided - cannot find nearby facilities")
            # Format a helpful message with the triage recommendation
            service_type_display = service_type.replace("_", " ").lower() if service_type else "healthcare facility"
            immediate_care_msg = ""
            if state.get("immediate_care"):
                immediate_care_msg = "\n\n⚠️ **This requires immediate care - please seek help right away.**"
            
            return {
                "service_type": service_type,
                "immediate_care": state.get("immediate_care", False),
                "nearby_facilities": [],
                "selected_facility": None,
                "current_agent": "orientation",
                "should_end": True,
                "agent_output": (
                    f"Based on your symptoms, I recommend visiting a **{service_type_display}**.\n\n"
                    f"📍 To find the nearest facility, please provide your location (city name or coordinates)."
                    f"{immediate_care_msg}"
                )
            }
        
        # Handle STAY_HOME - no need to find facilities
        if service_type == "STAY_HOME":
            logger.info("✅ STAY_HOME recommendation - no facility search needed")
            return {
                "service_type": "STAY_HOME",  # Preserve service_type
                "immediate_care": False,
                "nearby_facilities": [],
                "selected_facility": None,
                "current_agent": "orientation",
                "should_end": True,
                "agent_output": (
                    "Based on your symptoms, you can **stay home and rest**.\n\n"
                    "Your condition appears to be mild and self-limiting. "
                    "Monitor your symptoms and seek medical care if they worsen."
                )
            }
        
        logger.info(f"📍 Finding facilities near ({lat}, {lon}) for service type: {service_type}")
        
        # Use existing find_nearby_facilities function
        facilities = find_nearby_facilities(lat, lon, service_type, radius_km=5)
        
        if facilities:
            selected_facility = facilities[0]  # Nearest one
            logger.info(f"✅ Found {len(facilities)} facilities, nearest: {selected_facility.get('name')}")
            
            # Format facility type for display
            facility_type_display = service_type.replace("_", " ").lower()
            if service_type == "URGENT_CARE":
                facility_type_display = "urgent care"
            elif service_type == "MENTAL_HEALTH":
                facility_type_display = "mental health facility"
            
            # Simple output - frontend will render clickable items
            output = f"Found {len(facilities)} nearby {facility_type_display} facilities. Click on any facility below to see the route on the map."
            
            # Format facilities as "places" for frontend compatibility
            # Frontend expects: {name, type, distance, latitude, longitude, address}
            places = []
            for facility in facilities:
                place = {
                    "name": facility.get("name", "Unknown"),
                    "type": facility.get("type", service_type.replace("_", " ").lower()),
                    "distance": round(facility.get("distance", 0), 2),
                    "latitude": facility.get("latitude"),
                    "longitude": facility.get("longitude")
                }
                # Add address if available
                if facility.get("address"):
                    place["address"] = facility.get("address")
                places.append(place)
            
            return {
                "service_type": service_type,  # Preserve service_type
                "immediate_care": state.get("immediate_care", False),  # Preserve immediate_care
                "nearby_facilities": facilities,  # Keep for backward compatibility
                "places": places,  # Frontend expects "places"
                "latitude": lat,  # User location for map
                "longitude": lon,  # User location for map
                "selected_facility": selected_facility,
                "current_agent": "orientation",
                "should_end": True,
                "agent_output": output
            }
        else:
            logger.warning(f"⚠️ No facilities found for {service_type}")
            facility_type_display = service_type.replace("_", " ").lower()
            return {
                "service_type": service_type,  # Preserve service_type
                "immediate_care": state.get("immediate_care", False),  # Preserve immediate_care
                "nearby_facilities": [],
                "selected_facility": None,
                "current_agent": "orientation",
                "should_end": True,
                "agent_output": f"No {facility_type_display} facilities found nearby. Please search manually or provide a different location."
            }
    except Exception as e:
        logger.error(f"Error in orientation node: {e}", exc_info=True)
        return {
            "service_type": state.get("service_type", ""),  # Preserve service_type if available
            "immediate_care": state.get("immediate_care", False),
            "nearby_facilities": [],
            "selected_facility": None,
            "current_agent": "orientation",
            "should_end": True,
            "agent_output": f"Error finding facilities: {str(e)}"
        }

