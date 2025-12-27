import json
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import pickle
import re

# -----------------------------
# LOAD EMBEDDINGS & METADATA
# -----------------------------
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Full KB
index = faiss.read_index("full_medical_index.faiss")
with open("full_medical_metadata.pkl", "rb") as f:
    metadata = pickle.load(f)

# -----------------------------
# BUILD FAST KB (Top Prevalence)
# -----------------------------
prevalence_order = {
    "very common": 4,
    "common": 3,
    "uncommon": 2,
    "rare": 1,
    "very rare": 0
}

def map_prevalence(value):
    if not value:
        return -1
    v = value.lower().strip()
    for key in prevalence_order:
        if v.startswith(key):
            return prevalence_order[key]
    return -1

metadata_sorted = sorted(metadata, key=lambda c: map_prevalence(c.get("prevalence")), reverse=True)
fast_metadata = metadata_sorted[:25]

# Ensure "symptoms" are included in metadata
for m in fast_metadata + metadata:
    if "symptoms" not in m:
        m["symptoms"] = []

fast_texts = [m.get("formatted_text", "") for m in fast_metadata]
fast_embeddings = embedder.encode(fast_texts, normalize_embeddings=True).astype("float32")

fast_index = faiss.IndexFlatIP(fast_embeddings.shape[1])
fast_index.add(fast_embeddings)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def preprocess_symptoms(meta_list):
    for m in meta_list:
        symptoms = m.get("symptoms", [])
        if isinstance(symptoms, str):
            symptoms = [symptoms]
        m["_symptoms_lower"] = set(
            s.lower() for s in symptoms if isinstance(s, str)
        )

preprocess_symptoms(metadata)
preprocess_symptoms(fast_metadata)

import torch

@torch.no_grad()
def embed_query(text):
    return embedder.encode(
        text,
        normalize_embeddings=True,
        convert_to_numpy=True
    ).astype("float32")

def extract_symptoms_from_text(text):
    parts = re.split(r",| and |;", text.lower())
    return [p.strip() for p in parts if len(p.strip()) > 1]

def safe_extract_symptoms(meta):
    """Extract all original symptoms from metadata without deduplication"""
    symptoms = meta.get("symptoms", [])
    if isinstance(symptoms, str):
        symptoms = [symptoms]
    return [s.lower() for s in symptoms if isinstance(s, str)]

def symptom_overlap_score_improved(user_symptoms, disease_symptoms_set):
    """Improved overlap calculation with partial matching"""
    if not user_symptoms or not disease_symptoms_set:
        return 0.0
    
    matches = 0
    for user_symptom in user_symptoms:
        user_symptom_lower = user_symptom.lower()
        
        # Check for exact or partial matches
        for disease_symptom in disease_symptoms_set:
            disease_symptom_lower = disease_symptom.lower()
            
            # Multiple matching strategies
            if (user_symptom_lower == disease_symptom_lower or  # Exact match
                user_symptom_lower in disease_symptom_lower or  # User symptom is substring of disease symptom
                disease_symptom_lower in user_symptom_lower or  # Disease symptom is substring of user symptom
                any(word in disease_symptom_lower for word in user_symptom_lower.split()) or  # Word overlap
                any(word in user_symptom_lower for word in disease_symptom_lower.split())):
                
                matches += 1
                break  # Found a match for this user symptom
    
    return matches / len(user_symptoms)


def retrieve_conditions_faiss(query, top_k=5, use_fast_kb=False, user_age_group="young"):
    if use_fast_kb:
        idx = fast_index
        meta_list = fast_metadata
    else:
        idx = index
        meta_list = metadata

    # 1️⃣ fast embedding
    query_emb = embed_query(query).reshape(1, -1)

    # 2️⃣ Get MORE FAISS hits than needed for better filtering
    search_k = min(top_k * 3, len(meta_list))  # Get 3x more than needed
    similarities, indices = idx.search(query_emb, search_k)

    user_symptoms = extract_symptoms_from_text(query)
    retrieved = []

    for idx_i, faiss_score in zip(indices[0], similarities[0]):
        if idx_i >= len(meta_list):
            continue

        meta = meta_list[idx_i]
        original_symptoms = safe_extract_symptoms(meta)
        disease_symptoms_set = meta.get("_symptoms_lower", set())
        
        # Use improved overlap calculation
        overlap = symptom_overlap_score_improved(user_symptoms, disease_symptoms_set)
        
        prevalence_score = map_prevalence(meta.get("prevalence"))
        age_risk_score = meta.get(f"{user_age_group}_risk_score", 0)  # Default 0 instead of -1
        
        prevalence_bonus = prevalence_score * 0.05  # 0.05 per level
        
        # Base weights can adjust based on query quality
        if len(user_symptoms) >= 3:  # Good query, prioritize overlap
            faiss_weight = 0.4
            overlap_weight = 0.4
            age_weight = 0.15
        else:  # Poor query, rely more on semantic search
            faiss_weight = 0.6
            overlap_weight = 0.3
            age_weight = 0.05
        
        # Calculate combined score
        combined = (
            faiss_weight * float(faiss_score)
            + overlap_weight * overlap
            + age_weight * (age_risk_score / 5.0 if age_risk_score > 0 else 0)  # Normalize to 0-1
            + prevalence_bonus
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
            "prevalence_score": prevalence_score,
            "age_risk_score": age_risk_score,
            "combined_score": combined,
            "prevalence": meta.get("prevalence", "Unknown"),
            "risk_factors_age": meta.get("risk_factors_age", {}),
            "formatted_text": meta.get("formatted_text", ""),
            # Add diagnostic info
            "user_symptoms_matched": overlap * len(user_symptoms) if user_symptoms else 0,
            "total_symptoms": len(original_symptoms)
        })

    # 3️⃣ SORT FIRST, then take top_k
    retrieved.sort(key=lambda x: x["combined_score"], reverse=True)
    
    # 4️⃣ DIVERSITY: Avoid returning too many similar conditions
    final_results = []
    seen_categories = set()
    
    for condition in retrieved:
        # Simple deduplication by name
        name = condition["name"].lower()
        if any(name in seen_name or seen_name in name 
               for seen_name in seen_categories):
            continue
        
        seen_categories.add(name)
        final_results.append(condition)
        
        if len(final_results) >= top_k:
            break
    
    # 5️⃣ If we don't have enough diverse results, add more
    if len(final_results) < top_k:
        for condition in retrieved:
            if condition not in final_results:
                final_results.append(condition)
            if len(final_results) >= top_k:
                break

    return final_results[:top_k]


# -----------------------------
# DEBUG FUNCTION
# -----------------------------
def debug_symptom_extraction():
    """Debug symptom extraction to see where count drops"""
    print("\n=== 🐛 DEBUGGING SYMPTOM EXTRACTION ===")
    
    # Test with a few conditions
    test_conditions = metadata[:3]
    
    for i, condition in enumerate(test_conditions):
        print(f"\n--- Condition {i+1}: {condition.get('name')} ---")
        
        # Original symptoms from metadata
        original_symptoms = condition.get("symptoms", [])
        if isinstance(original_symptoms, str):
            original_symptoms = [original_symptoms]
        print(f"Original symptom count: {len(original_symptoms)}")
        print(f"Original symptoms (first 10): {original_symptoms[:10]}")
        
        # What preprocess_symptoms created
        preprocessed = condition.get("_symptoms_lower", set())
        print(f"Preprocessed count: {len(preprocessed)}")
        print(f"Preprocessed: {list(preprocessed)[:10]}")
        
        # What safe_extract_symptoms would return
        safe_extracted = safe_extract_symptoms(condition)
        print(f"Safe extract count: {len(safe_extracted)}")
        print(f"Safe extracted: {safe_extracted[:10]}")
        
        # Check for duplicates in original
        if len(original_symptoms) != len(set(s.lower() for s in original_symptoms if isinstance(s, str))):
            print("⚠️  Duplicates detected in original symptoms!")

    # Check symptom count distribution
    print("\n=== 📊 SYMPTOM COUNT DISTRIBUTION ===")
    symptom_counts = []
    for condition in metadata[:100]:  # Check first 100 conditions
        symptoms = safe_extract_symptoms(condition)
        symptom_counts.append(len(symptoms))
    
    from collections import Counter
    count_dist = Counter(symptom_counts)
    print("\nTop symptom counts:")
    for count, freq in sorted(count_dist.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {count} symptoms: {freq} conditions")
    
    print(f"\nMax symptoms: {max(symptom_counts)}")
    print(f"Min symptoms: {min(symptom_counts)}")
    print(f"Average: {sum(symptom_counts)/len(symptom_counts):.1f}")


# -----------------------------
# TESTER
# -----------------------------
if __name__ == "__main__":
    # Run debug first
    debug_symptom_extraction()
    
    print("\n" + "="*50)
    print("=== 🔍 RAG TESTER ===")
    print("="*50)
    
    test_query = "fever, headache, sore throat"
    print(f"\nQuery: '{test_query}'")
    
    print("\n--- Fast KB Results (Top 3) ---")
    fast_results = retrieve_conditions_faiss(test_query, top_k=3, use_fast_kb=True)
    for i, r in enumerate(fast_results, 1):
        print(f"\n{i}. {r['name']}")
        print(f"   Combined Score: {r['combined_score']:.3f}")
        print(f"   Symptom Count: {len(r['symptoms'])}")
        print(f"   Symptoms (first 8): {r['symptoms'][:8]}")
    
    print("\n--- Full KB Results (Top 3) ---")
    full_results = retrieve_conditions_faiss(test_query, top_k=3, use_fast_kb=False)
    for i, r in enumerate(full_results, 1):
        print(f"\n{i}. {r['name']}")
        print(f"   Combined Score: {r['combined_score']:.3f}")
        print(f"   Symptom Count: {len(r['symptoms'])}")
        print(f"   Symptoms (first 8): {r['symptoms'][:8]}")
    
    # Test with different age groups
    print("\n" + "="*50)
    print("=== 👥 AGE GROUP TESTING ===")
    print("="*50)
    
    print("\n--- Young Patient Results ---")
    young_results = retrieve_conditions_faiss("fever, headache", top_k=2, user_age_group="young")
    for r in young_results:
        print(f"{r['name']} - Age Risk: {r['age_risk_score']}")

    print("\n--- Older Patient Results ---")
    old_results = retrieve_conditions_faiss("fever, headache", top_k=2, user_age_group="old")
    for r in old_results:
        print(f"{r['name']} - Age Risk: {r['age_risk_score']}")
    
    # Test symptom overlap
    print("\n" + "="*50)
    print("=== 🔄 SYMPTOM OVERLAP TEST ===")
    print("="*50)
    
    test_cases = [
        "fever, cough, fatigue",
        "chest pain, shortness of breath",
        "headache, nausea, dizziness"
    ]
    
    for query in test_cases:
        print(f"\nQuery: '{query}'")
        results = retrieve_conditions_faiss(query, top_k=1)
        if results:
            r = results[0]
            print(f"  Top match: {r['name']}")
            print(f"  Overlap score: {r['overlap_score']:.2f}")
            print(f"  Matching symptoms: {set(extract_symptoms_from_text(query)) & set(s.lower() for s in r['symptoms'])}")