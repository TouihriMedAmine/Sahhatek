# agents/triage_agent/diagnosis_node_rewrite.py
"""
Complete rewrite of diagnosis_node with multi-turn Q&A support
"""

import json
import re
import uuid
import logging
from typing import Dict, Any, List, Set
from .diagnosis_logic import (
    get_diagnosis_helpers,
    calculate_diagnosis_confidence,
    generate_questions_from_diagnoses,
    process_answer
)

logger = logging.getLogger(__name__)

# Global diagnosis sessions
_diagnosis_sessions: Dict[str, Dict] = {}

CONFIDENCE_THRESHOLD = 0.97
MAX_DIAGNOSIS_TURNS = 10

def diagnosis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Multi-turn Q&A diagnosis node.
    
    Flow:
    1. Check for pending_questions (answer from previous turn)
    2. If yes, process answer and update symptoms
    3. Generate/update diagnoses
    4. Check confidence threshold
    5. If < threshold: generate questions, set pending_questions, loop back
    6. If >= threshold: return diagnosis and proceed to triage
    """
    logger.info("🩺 DIAGNOSIS NODE: Multi-turn Q&A")
    
    try:
        # Get helpers
        helpers = get_diagnosis_helpers()
        normalize_symptom_func = helpers["normalize_symptom"]
        determine_age_group_func = helpers["determine_age_group"]
        retrieve_conditions_faiss = helpers["retrieve_conditions_faiss"]
        
        # Get state
        symptoms = state.get("symptoms", [])
        negative_symptoms = state.get("negative_symptoms", [])
        user_input = state.get("user_input", "")
        pending_questions = state.get("pending_questions", [])
        diagnosis_session_id = state.get("diagnosis_session_id")
        
        # Check if this is an answer to a pending question
        is_answer = bool(pending_questions) and user_input
        
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
        else:
            session = _diagnosis_sessions.get(diagnosis_session_id, {})
            symptoms = list(session.get("positive_symptoms", []))
            negative_symptoms = list(session.get("negative_symptoms", []))
        
        session = _diagnosis_sessions[diagnosis_session_id]
        
        # Process answer if this is a response to a question
        if is_answer and pending_questions:
            question = pending_questions[0]  # Get first pending question
            answer = user_input
            
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
        
        if not symptoms:
            return {
                "disease": "unknown",
                "severity": "moderate",
                "confidence": 0.5,
                "current_agent": "diagnosis",
                "agent_output": "No symptoms provided"
            }
        
        # Determine age group
        user_context = state.get("metadata", {}).get("user_context", {})
        age_input = user_context.get("age") or "adult"
        user_age_group = determine_age_group_func(str(age_input))
        
        # Normalize symptoms
        normalized_symptoms = [normalize_symptom_func(s) for s in symptoms]
        normalized_negative = [normalize_symptom_func(s) for s in negative_symptoms]
        
        # Retrieve conditions
        symptoms_text = " ".join(normalized_symptoms)
        conditions = retrieve_conditions_faiss(symptoms_text, top_k=15, user_age_group=user_age_group)
        
        if not conditions:
            return {
                "disease": "unknown",
                "severity": "moderate",
                "confidence": 0.5,
                "current_agent": "diagnosis",
                "agent_output": "No matching conditions found"
            }
        
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
            response = client.chat.completions.create(
                model="hosted_vllm/Llama-3.1-70B-Instruct",
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
                    "diagnosis_complete": True,
                    "current_agent": "diagnosis",
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
                        "diagnosis_complete": True,
                        "current_agent": "diagnosis",
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
                    "current_agent": "diagnosis",
                    "should_end": False,  # Don't end - need user answer
                    "agent_output": (
                        f"I need to ask you a question to better understand your condition "
                        f"and provide an accurate diagnosis:\n\n{question}"
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

