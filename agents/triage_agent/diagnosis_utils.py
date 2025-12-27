# agents/triage_agent/diagnosis_utils.py
"""
Independent diagnosis utilities - no dependency on triage app
"""

import re
import json
import os
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Get the agent's directory
_agent_dir = Path(__file__).parent
_project_root = _agent_dir.parent.parent

# Use agent's own data directory (fully independent)
_data_dir = _agent_dir / "data"

# Initialize embedder at module level (once, reused for all calls)
_embedder = None
_faiss_index_cache = {}  # Cache for FAISS indexes

def init_kb() -> bool:
    """Quick initialization for knowledge base at app startup"""
    return initialize_knowledge_base()

def initialize_knowledge_base() -> bool:
    """
    Pre-initialize embedder and FAISS indexes for maximum performance.
    Call this once at app startup to avoid lazy loading delays.
    """
    global _embedder, _faiss_index_cache
    
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
        import pickle
        
        print("[KB] Loading SentenceTransformer embedder...")
        
        # Initialize embedder
        if _embedder is None:
            _embedder = SentenceTransformer('all-MiniLM-L6-v2')
            print("[KB] Embedder ready")
        
        # Pre-load both indexes
        for kb_name, use_fast in [("full", False), ("fast", True)]:
            cache_key = f"{'fast' if use_fast else 'full'}_index"
            if cache_key not in _faiss_index_cache:
                index_path = _data_dir / (f"fast_medical_index.faiss" if use_fast else "full_medical_index.faiss")
                metadata_path = _data_dir / (f"fast_medical_metadata.pkl" if use_fast else "full_medical_metadata.pkl")
                
                if index_path.exists() and metadata_path.exists():
                    print(f"[KB] Loading {kb_name} knowledge base...")
                    index = faiss.read_index(str(index_path))
                    with open(metadata_path, "rb") as f:
                        metadata = pickle.load(f)
                    
                    _faiss_index_cache[cache_key] = {
                        "index": index,
                        "metadata": metadata,
                        "path": str(index_path)
                    }
                    logger.info(f"Loaded {kb_name} KB: {len(metadata)} conditions")
                    print(f"[KB] {kb_name}: {len(metadata)} conditions ready")
        
        logger.info("Knowledge base initialization complete!")
        print("[KB] Pre-initialization complete - retrieval will be instant!")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing knowledge base: {e}", exc_info=True)
        return False

# ============================================================
# SYMPTOM NORMALIZATION
# ============================================================

def normalize_symptom(s: str) -> str:
    """Normalize symptom strings to avoid duplicates"""
    if not s:
        return ""
    s = s.lower().strip()
    s = s.replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    synonyms = {
        "fever": "high_temperature",
        "sudden high temperature": "high_temperature",
        "feeling tired": "fatigue",
        "aches and pains": "body_aches",
        "diarrhoea or tummy pain": "diarrhea",
        "diarrhea or tummy pain": "diarrhea",
        "headache": "headache",
        "sore throat": "sore_throat",
        "cough": "cough",
        "runny nose": "runny_nose",
        "nausea": "nausea",
        "vomiting": "vomiting",
        "chest pain": "chest_pain",
        "shortness of breath": "shortness_of_breath",
        "dizziness": "dizziness",
        "muscle pain": "muscle_pain",
        "joint pain": "joint_pain",
        "swollen glands": "swollen_glands",
        "rash": "rash",
        "itchy skin": "itchy_skin"
    }
    return synonyms.get(s, s.replace(" ", "_"))

# ============================================================
# AGE GROUP DETERMINATION
# ============================================================

def determine_age_group(age_input) -> str:
    """Convert age input to age group for medical context"""
    if not age_input:
        return "adult"
    
    try:
        age = int(age_input)
        if age <= 12:
            return "child"
        elif age <= 18:
            return "young"
        elif age < 65:
            return "adult"
        else:
            return "old"
    except (ValueError, TypeError):
        # Handle text inputs
        age_lower = str(age_input).lower()
        if any(x in age_lower for x in ["child", "kid", "baby", "infant", "toddler"]):
            return "child"
        elif any(x in age_lower for x in ["teen", "adolescent", "young"]):
            return "young"
        elif any(x in age_lower for x in ["old", "senior", "elderly", "retired"]):
            return "old"
        else:
            return "adult"

def symptom_overlap_score_improved(user_symptoms: List[str], disease_symptoms_set: set) -> float:
    """
    Improved overlap calculation with multiple matching strategies
    (Aligned with retrival.py for consistency)
    """
    if not user_symptoms or not disease_symptoms_set:
        return 0.0
    
    matches = 0
    for user_symptom in user_symptoms:
        user_symptom_lower = user_symptom.lower()
        
        # Multiple matching strategies
        for disease_symptom in disease_symptoms_set:
            disease_symptom_lower = disease_symptom.lower()
            
            if (user_symptom_lower == disease_symptom_lower or  # Exact match
                user_symptom_lower in disease_symptom_lower or  # Substring match
                disease_symptom_lower in user_symptom_lower or  # Reverse substring
                any(word in disease_symptom_lower for word in user_symptom_lower.split()) or  # Word overlap
                any(word in user_symptom_lower for word in disease_symptom_lower.split())):  # Reverse word overlap
                
                matches += 1
                break  # Found a match for this user symptom
    
    return matches / len(user_symptoms)

# ============================================================
# FAISS RETRIEVAL (Independent Implementation)
# ============================================================

def retrieve_conditions_faiss(query: str, top_k: int = 10, use_fast_kb: bool = False, user_age_group: str = "adult") -> List[Dict]:
    """
    Retrieve medical conditions from FAISS index with improved scoring.
    Uses pre-cached index if available, falls back to lazy loading.
    For best performance, call initialize_knowledge_base() at app startup.
    """
    try:
        import numpy as np
        
        cache_key = f"{'fast' if use_fast_kb else 'full'}_index"
        
        # Use cached index if available
        if cache_key in _faiss_index_cache:
            cached = _faiss_index_cache[cache_key]
            index = cached["index"]
            metadata = cached["metadata"]
            logger.debug(f"Using cached {cache_key} KB index")
        else:
            # Fallback to lazy loading
            from sentence_transformers import SentenceTransformer
            import faiss
            import pickle
            
            index_path = _data_dir / ("fast_medical_index.faiss" if use_fast_kb else "full_medical_index.faiss")
            metadata_path = _data_dir / ("fast_medical_metadata.pkl" if use_fast_kb else "full_medical_metadata.pkl")
            
            if not index_path.exists() or not metadata_path.exists():
                logger.warning(f"FAISS index not found at {index_path}, falling back to JSON search")
                return retrieve_conditions_json(query, top_k, user_age_group)
            
            logger.info(f"Lazy loading FAISS index: {index_path}")
            index = faiss.read_index(str(index_path))
            with open(metadata_path, "rb") as f:
                metadata = pickle.load(f)
            
            # Cache for future use
            _faiss_index_cache[cache_key] = {
                "index": index,
                "metadata": metadata,
                "path": str(index_path)
            }
        
        # Preprocess symptoms for faster matching
        for m in metadata:
            symptoms = m.get("symptoms", [])
            if isinstance(symptoms, str):
                symptoms = [symptoms]
            m["_symptoms_lower"] = set(s.lower() for s in symptoms if isinstance(s, str))
            if "symptoms" not in m:
                m["symptoms"] = []
        
        # Encode query
        global _embedder
        if _embedder is None:
            # Lazy load embedder if not pre-initialized
            try:
                from sentence_transformers import SentenceTransformer
                print("[KB] Lazy-loading embedder (consider calling init_kb() at startup for better performance)")
                _embedder = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                logger.error(f"Failed to initialize embedder: {e}")
                return retrieve_conditions_json(query, top_k, user_age_group)
        
        query_embedding = _embedder.encode([query], normalize_embeddings=True).astype("float32")
        
        # Search - get more results for better filtering
        search_k = min(top_k * 3, len(metadata))
        distances, indices = index.search(query_embedding.reshape(1, -1), search_k)
        
        # Extract symptoms from query
        user_symptoms = [s.strip() for s in query.lower().split(",") if s.strip()]
        
        # Score and rank results with improved logic
        retrieved = []
        for idx, faiss_score in zip(indices[0], distances[0]):
            if idx >= len(metadata):
                continue
            
            meta = metadata[idx]
            original_symptoms = meta.get("symptoms", [])
            if isinstance(original_symptoms, str):
                original_symptoms = [original_symptoms]
            original_symptoms = [s.lower() for s in original_symptoms if isinstance(s, str)]
            disease_symptoms_set = meta.get("_symptoms_lower", set())
            
            # Calculate symptom overlap using improved matching
            overlap = symptom_overlap_score_improved(user_symptoms, disease_symptoms_set)
            
            # Get prevalence score
            prevalence = meta.get("prevalence", "").lower()
            prevalence_score = -1
            if prevalence:
                if "very common" in prevalence:
                    prevalence_score = 4
                elif "common" in prevalence:
                    prevalence_score = 3
                elif "uncommon" in prevalence:
                    prevalence_score = 2
                elif "rare" in prevalence:
                    prevalence_score = 1
                else:
                    prevalence_score = 0
            
            # Get age risk score
            age_risk_score = meta.get(f"{user_age_group}_risk_score", 0)
            prevalence_bonus = prevalence_score * 0.05 if prevalence_score >= 0 else 0
            
            # Determine weights based on query quality
            if len(user_symptoms) >= 3:
                faiss_weight = 0.4
                overlap_weight = 0.4
                age_weight = 0.15
            else:
                faiss_weight = 0.6
                overlap_weight = 0.3
                age_weight = 0.05
            
            # Calculate combined score (ALIGNED WITH retrival.py)
            combined = (
                faiss_weight * float(faiss_score) +
                overlap_weight * overlap +
                age_weight * (age_risk_score / 5.0 if age_risk_score > 0 else 0) +
                prevalence_bonus
            )
            
            # Bonus for high overlap
            if overlap >= 0.8:
                combined += 0.1
            elif overlap >= 0.5:
                combined += 0.05
            
            retrieved.append({
                "name": meta.get("name", "Unknown"),
                "symptoms": original_symptoms,
                "canonical_symptoms": original_symptoms,
                "faiss_score": float(faiss_score),
                "overlap_score": overlap,
                "combined_score": combined,
                "prevalence": meta.get("prevalence", "Unknown"),
                "age_relevance": meta.get("age_relevance", "unknown"),
                "age_risk_score": age_risk_score,
                "formatted_text": meta.get("formatted_text", ""),
                "similarity_score": float(faiss_score)
            })
        
        # Sort by combined score
        retrieved.sort(key=lambda x: x["combined_score"], reverse=True)
        print(retrieved[0]["combined_score"])
        print(retrieved[0]["age_relevance"])
        print(retrieved[0]["age_risk_score"])
        # Diversity: avoid too many similar conditions
        final_results = []
        seen_categories = set()
        
        for condition in retrieved:
            name = condition["name"].lower()
            if any(name in seen_name or seen_name in name for seen_name in seen_categories):
                continue
            seen_categories.add(name)
            final_results.append(condition)
            if len(final_results) >= top_k:
                break
        
        # Fill remaining slots if needed
        if len(final_results) < top_k:
            for condition in retrieved:
                if condition not in final_results:
                    final_results.append(condition)
                if len(final_results) >= top_k:
                    break
        
        logger.info(f"Retrieved {len(final_results)} conditions from FAISS with improved scoring")
        return final_results[:top_k]
            
    except ImportError as e:
        logger.warning(f"FAISS dependencies not available: {e}, falling back to JSON search")
        return retrieve_conditions_json(query, top_k, user_age_group)
    except Exception as e:
        logger.error(f"Error retrieving from FAISS: {e}", exc_info=True)
        return retrieve_conditions_json(query, top_k, user_age_group)

def retrieve_conditions_json(query: str, top_k: int = 10, user_age_group: str = "adult") -> List[Dict]:
    """
    Fallback: Retrieve conditions from JSON file using simple text matching
    """
    try:
        json_path = _data_dir / "nhs_conditions2.json"
        if not json_path.exists():
            logger.warning(f"JSON file not found at {json_path}")
            return []
        
        with open(json_path, 'r', encoding='utf-8') as f:
            conditions = json.load(f)
        
        if not isinstance(conditions, list):
            conditions = list(conditions.values()) if isinstance(conditions, dict) else []
        
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        # Score conditions by keyword matching
        scored = []
        for condition in conditions:
            score = 0
            name = condition.get("name", "").lower()
            symptoms = condition.get("symptoms", [])
            if isinstance(symptoms, str):
                symptoms = [symptoms]
            symptoms_text = " ".join([s.lower() for s in symptoms if isinstance(s, str)])
            
            # Check name
            for term in query_terms:
                if term in name:
                    score += 2
                if term in symptoms_text:
                    score += 1
            
            if score > 0:
                scored.append((score, condition))
        
        # Sort by score
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Filter by age group
        results = []
        for score, condition in scored[:top_k * 2]:  # Get more to filter
            age_info = condition.get("age_relevance", "").lower()
            if user_age_group == "adult" or user_age_group in age_info or age_info == "all" or not age_info:
                results.append(condition)
                if len(results) >= top_k:
                    break
        
        logger.info(f"Retrieved {len(results)} conditions from JSON")
        return results
        
    except Exception as e:
        logger.error(f"Error retrieving from JSON: {e}", exc_info=True)
        return []

# ============================================================
# DIAGNOSIS GENERATION (LLM-based)
# ============================================================

def generate_diagnosis_llm(positive_symptoms: List[str], negative_symptoms: List[str], 
                          negative_diseases: List[str], user_age_group: str = "adult",
                          expand_search: bool = False, llm_client=None) -> Dict:
    """
    Generate diagnosis using LLM with FAISS retrieval.
    Independent implementation - no dependency on triage app.
    """
    if not positive_symptoms:
        return {"diagnoses": []}
    
    # Retrieve conditions using FAISS
    query_text = " ".join(positive_symptoms)
    conditions = retrieve_conditions_faiss(query_text, top_k=15 if expand_search else 10, user_age_group=user_age_group)
    
    if not conditions:
        return {"diagnoses": []}
    
    # Format conditions for LLM
    conditions_text = "\n".join([
        f"{i+1}. {c.get('name', 'Unknown')} (symptoms: {', '.join(c.get('symptoms', [])[:3])})"
        for i, c in enumerate(conditions[:10])
    ])
    
    # Create prompt
    age_context = f"\nPatient age group: {user_age_group}." if user_age_group else ""
    
    prompt = f"""You are a medical assistant helping to diagnose patients.

Patient positive symptoms: {positive_symptoms}
Patient absent symptoms: {negative_symptoms}
Diseases ruled out: {negative_diseases if negative_diseases else "None"}{age_context}

Relevant medical conditions:
{conditions_text}

Task:
- Identify top 3-5 likely diagnoses from the list above.
- Use positive and negative symptoms to adjust confidence scores (0.0 to 1.0).
- Return valid JSON with this format:
{{
  "diagnoses": [
    {{
      "name": "Condition Name",
      "confidence": 0.75,
      "canonical_symptoms": ["symptom1", "symptom2"],
      "age_relevance": "high"
    }}
  ]
}}"""

    if not llm_client:
        # Fallback: return top condition
        return {
            "diagnoses": [{
                "name": conditions[0].get("name", "Unknown"),
                "confidence": 0.6,
                "canonical_symptoms": conditions[0].get("symptoms", []),
                "age_relevance": "medium"
            }]
        }
    
    try:
        # Get model name
        # Check if it's a Groq client by checking the type
        is_groq = 'groq' in str(type(llm_client)).lower() or hasattr(llm_client, 'models')
        if is_groq:
            # Use working Groq model
            model_name = "meta-llama/llama-4-scout-17b-16e-instruct"
        else:  # OpenAI-compatible client
            # Use a standard OpenAI model or fallback to Groq model
            model_name = "meta-llama/llama-4-scout-17b-16e-instruct"
        
        response = llm_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a medical assistant. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        
        content = response.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        
        if json_match:
            result = json.loads(json_match.group())
            diagnoses = result.get("diagnoses", [])
            if diagnoses:
                return {"diagnoses": diagnoses}
        
        # Fallback
        return {
            "diagnoses": [{
                "name": conditions[0].get("name", "Unknown"),
                "confidence": 0.6,
                "canonical_symptoms": conditions[0].get("symptoms", []),
                "age_relevance": "medium"
            }]
        }
    except Exception as e:
        logger.error(f"Error in LLM diagnosis: {e}")
        return {
            "diagnoses": [{
                "name": conditions[0].get("name", "Unknown") if conditions else "Unknown",
                "confidence": 0.5,
                "canonical_symptoms": conditions[0].get("symptoms", []) if conditions else [],
                "age_relevance": "medium"
            }]
        }

