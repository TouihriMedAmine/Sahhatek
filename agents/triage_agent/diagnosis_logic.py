# agents/triage_agent/diagnosis_logic.py
"""
Helper functions for diagnosis node multi-turn Q&A
Aligned with agent3.py diagnosis pipeline
"""

import json
import re
import os
import logging
from typing import Dict, Any, List, Set
from pathlib import Path
import importlib.util
import sys

logger = logging.getLogger(__name__)

# Store for LangSmith logging (optional)
_diagnosis_events = []

def log_to_langsmith(event_name: str, payload: dict):
    """Helper function to log diagnostic events"""
    global _diagnosis_events
    _diagnosis_events.append({
        "event": event_name,
        "data": payload
    })

def get_diagnosis_helpers():
    """Get diagnosis helper functions from independent module"""
    try:
        from .diagnosis_utils import (
            normalize_symptom,
            determine_age_group,
            retrieve_conditions_faiss
        )
        return {
            "normalize_symptom": normalize_symptom,
            "determine_age_group": determine_age_group,
            "retrieve_conditions_faiss": retrieve_conditions_faiss
        }
    except Exception as e:
        logger.warning(f"Could not import diagnosis utils: {e}", exc_info=True)
        # Fallback functions
        def normalize_symptom(s: str) -> str:
            s = s.lower().strip().replace("-", " ")
            s = re.sub(r"\s+", " ", s)
            # Basic symptom synonym normalization
            synonyms = {
                "fever": "high temperature",
                "sudden high temperature": "high temperature",
                "feeling tired": "fatigue",
                "aches and pains": "body aches",
                "diarrhoea or tummy pain": "diarrhea",
            }
            return synonyms.get(s, s)
        
        def determine_age_group(age_input: str) -> str:
            try:
                age = int(age_input)
                if age <= 18:
                    return "young"
                elif age < 45:
                    return "adult"
                else:
                    return "old"
            except:
                return "adult"
        
        def retrieve_conditions_faiss(query, top_k=10, user_age_group="adult"):
            return []
        
        return {
            "normalize_symptom": normalize_symptom,
            "determine_age_group": determine_age_group,
            "retrieve_conditions_faiss": retrieve_conditions_faiss
        }

def calculate_diagnosis_confidence(
    diagnosis: dict,
    positive_symptoms: List[str],
    negative_symptoms: List[str],
    age_group: str,
    normalize_symptom_func,
    previous_confidence: Dict[str, float] = None
) -> float:
    """Calculate confidence using exact formula (aligned with agent3.py)"""
    if previous_confidence is None:
        previous_confidence = {}
    
    name = diagnosis.get("name", "Unknown")
    canonical_symptoms = diagnosis.get("canonical_symptoms", [])
    
    # Normalize all symptoms
    normalized_canonical = [normalize_symptom_func(cs) for cs in canonical_symptoms]
    normalized_positive = [normalize_symptom_func(ps) for ps in positive_symptoms]
    normalized_negative = [normalize_symptom_func(ns) for ns in negative_symptoms]
    
    # Count matches
    num_present = 0
    for pos_symptom in normalized_positive:
        for canon_symptom in normalized_canonical:
            if pos_symptom in canon_symptom or canon_symptom in pos_symptom:
                num_present += 1
                break
    
    num_absent = 0
    for neg_symptom in normalized_negative:
        for canon_symptom in normalized_canonical:
            if neg_symptom in canon_symptom or canon_symptom in neg_symptom:
                num_absent += 1
                break
    
    # Age relevance (from diagnosis if available)
    age_relevance = diagnosis.get("age_relevance", "medium")
    age_bonus = {"high": 0.03, "medium": 0.0, "low": -0.02}.get(age_relevance, 0.0)

    # Coverage bonus
    expected_symptoms = len(canonical_symptoms)
    coverage_bonus = 0.0
    if expected_symptoms > 0:
        coverage_ratio = num_present / expected_symptoms
        if coverage_ratio >= 0.9:
            coverage_bonus = 0.12
        elif coverage_ratio >= 0.75:
            coverage_bonus = 0.07
        elif coverage_ratio >= 0.6:
            coverage_bonus = 0.03
    
    # Positive symptom bonus (reward for matching positive symptoms)
    positive_bonus = 0.0
    if num_present > 0:
        positive_bonus = num_present * 0.05  # +0.05 per positive symptom matched
    
    # Use previous confidence if available, otherwise default
    prev_conf = previous_confidence.get(name, diagnosis.get("confidence", 0.5))
    
    # Confidence calculation (IMPROVED FORMULA WITH POSITIVE BONUS)
    confidence = max(0, min(1,
        prev_conf
        + positive_bonus          # REWARD for positive symptoms matched
        - 0.03 * num_absent      # PENALTY for negative symptoms present
        + age_bonus
        + coverage_bonus          # High coverage reward
    ))
    print(f"Diagnosis '{name}': +{num_present} present, -{num_absent} absent, age_bonus={age_bonus}, coverage_bonus={coverage_bonus} => confidence={confidence:.3f}")
    # Log to LangSmith: confidence change for each diagnosis
    log_to_langsmith("confidence_update", {
        "diagnosis": name,
        "previous_confidence": prev_conf,
        "new_confidence": confidence,
        "confidence_change": confidence - prev_conf,
        "positive_symptoms_matched": num_present,
        "negative_symptoms_matched": num_absent,
        "coverage_ratio": num_present / expected_symptoms if expected_symptoms > 0 else 0,
        "age_bonus": age_bonus,
        "coverage_bonus": coverage_bonus,
        "total_canonical_symptoms": expected_symptoms
    })
    
    return confidence

def generate_questions_from_diagnoses(
    top_diagnoses: List[dict],
    already_asked: Set[str],
    normalize_symptom_func
) -> List[str]:
    """Generate questions about symptoms from top diagnoses (aligned with agent3.py)"""
    questions = []
    
    # Extract symptoms from top diagnoses (prioritizing highest confidence)
    for diagnosis in top_diagnoses:
        canonical_symptoms = diagnosis.get("canonical_symptoms", [])
        
        for symptom in canonical_symptoms:
            if isinstance(symptom, str):
                normalized = normalize_symptom_func(symptom)
                
                if normalized not in already_asked:
                    symptom_text = normalized.replace('_', ' ').replace('-', ' ')
                    question = f"Do you have {symptom_text}?"
                    
                    if question not in questions:
                        questions.append(question)
                    
                    if len(questions) >= 3:  # Limit to 3 questions per turn
                        return questions
    
    return questions

def process_answer(
    question: str,
    answer: str,
    normalize_symptom_func
) -> tuple:
    """Process yes/no answer and return (symptom, is_positive)"""
    answer_lower = answer.lower().strip()
    
    # Extract symptom from question
    symptom_text = question.replace("Do you have ", "").replace("?", "").strip()
    symptom_normalized = normalize_symptom_func(symptom_text)
    
    # Check if yes or no
    if answer_lower in ['yes', 'y', 'yeah', 'yep', 'sure', 'correct', 'right', 'affirmative']:
        return (symptom_normalized, True)
    elif answer_lower in ['no', 'n', 'nope', 'nah', 'negative', 'not']:
        return (symptom_normalized, False)
    else:
        # Try to extract symptoms from free text
        return (None, None)

def get_all_symptoms_from_conditions(conditions: List[dict]) -> Set[str]:
    """Extract ALL unique symptoms from retrieved conditions"""
    all_symptoms = set()
    for condition in conditions:
        symptoms = condition.get("symptoms", [])
        # Ensure all symptoms are strings and normalized
        for symptom in symptoms:
            if isinstance(symptom, str):
                all_symptoms.add(symptom)
    return all_symptoms

def create_diagnosis_summary(final_state: Dict, _diagnosis_events: List = None) -> Dict:
    """Create a structured summary of the entire diagnosis process"""
    if _diagnosis_events is None:
        _diagnosis_events = []
    
    summary = {
        "metadata": {
            "total_turns": final_state.get("turn", 0),
            "total_questions_asked": len(final_state.get("asked_questions", [])),
            "total_symptoms_collected": len(final_state.get("asked_symptoms", [])),
            "positive_symptoms": len(final_state.get("positive_symptoms", [])),
            "negative_symptoms": len(final_state.get("negative_symptoms", [])),
            "max_confidence": final_state.get("max_confidence", 0.0),
            "user_age_group": final_state.get("user_age_group", "unknown")
        },
        "confidence_progression": {},
        "diagnoses": [],
        "summary_text": ""
    }
    
    # Extract confidence progression from events
    confidence_events = [e for e in _diagnosis_events if e["event"] == "confidence_update"]
    if confidence_events:
        diagnosis_progression = {}
        for event in confidence_events:
            diagnosis = event["data"]["diagnosis"]
            if diagnosis not in diagnosis_progression:
                diagnosis_progression[diagnosis] = []
            diagnosis_progression[diagnosis].append({
                "confidence": event["data"]["new_confidence"],
                "change": event["data"]["confidence_change"],
                "symptoms_matched": event["data"]["positive_symptoms_matched"]
            })
        summary["confidence_progression"] = diagnosis_progression
    
    # Extract final diagnoses
    if final_state.get("diagnoses"):
        summary["diagnoses"] = [
            {
                "rank": i + 1,
                "name": d.get("name", "Unknown"),
                "confidence": d.get("confidence", 0.0),
                "confidence_percent": f"{d.get('confidence', 0.0) * 100:.1f}%",
                "symptoms_matched": len([s for s in final_state.get("positive_symptoms", []) 
                                        if any(s in cs or cs in s for cs in d.get("canonical_symptoms", []))]),
                "total_canonical_symptoms": len(d.get("canonical_symptoms", []))
            }
            for i, d in enumerate(final_state.get("diagnoses", [])[:5])
        ]
    
    # Create human-readable summary
    summary_lines = [
        "=" * 70,
        "DIAGNOSIS SUMMARY REPORT",
        "=" * 70,
        "",
        "PROCESS METRICS:",
        f"  • Total Turns: {summary['metadata']['total_turns']}",
        f"  • Questions Asked: {summary['metadata']['total_questions_asked']}",
        f"  • Symptoms Collected: {summary['metadata']['total_symptoms_collected']}",
        f"    - Positive: {summary['metadata']['positive_symptoms']}",
        f"    - Negative: {summary['metadata']['negative_symptoms']}",
        f"  • Patient Age Group: {summary['metadata']['user_age_group']}",
        f"  • Max Confidence Reached: {summary['metadata']['max_confidence']:.1%}",
        "",
        "TOP DIAGNOSES:",
    ]
    
    if summary["diagnoses"]:
        for d in summary["diagnoses"]:
            summary_lines.append(f"  {d['rank']}. {d['name']}")
            summary_lines.append(f"     Confidence: {d['confidence_percent']}")
            summary_lines.append(f"     Symptoms Matched: {d['symptoms_matched']}/{d['total_canonical_symptoms']}")
    else:
        summary_lines.append("  No diagnoses generated")
    
    summary_lines.extend([
        "",
        "CONFIDENCE PROGRESSION:",
    ])
    
    if summary["confidence_progression"]:
        for diagnosis, progression in summary["confidence_progression"].items():
            summary_lines.append(f"  {diagnosis}:")
            for i, step in enumerate(progression[-3:], 1):
                summary_lines.append(f"    Step {i}: {step['confidence']:.1%} (change: {step['change']:+.1%})")
    else:
        summary_lines.append("  No confidence progression data")
    
    summary_lines.extend([
        "",
        "=" * 70,
    ])
    
    summary["summary_text"] = "\n".join(summary_lines)
    
    # Log the summary
    log_to_langsmith("diagnosis_summary", summary)
    
    return summary

