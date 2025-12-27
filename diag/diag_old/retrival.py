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
def extract_symptoms_from_text(text):
    parts = re.split(r",| and |;", text.lower())
    return [p.strip() for p in parts if len(p.strip()) > 1]

def safe_extract_symptoms(meta):
    symptoms = meta.get("symptoms", [])
    if isinstance(symptoms, str):
        symptoms = [symptoms]
    return [s.lower() for s in symptoms if isinstance(s, str)]

def symptom_overlap_score(user_symptoms, disease_symptoms):
    count = sum(s in disease_symptoms for s in user_symptoms)
    return count / max(len(user_symptoms), 1)

# -----------------------------
# RETRIEVAL FUNCTION WITH HYBRID KB
# -----------------------------
def retrieve_conditions_faiss(query, top_k=5, use_fast_kb=False, user_age_group="young"):
    """
    user_age_group: "young" or "old" to prioritize age-relevant conditions
    """
    if use_fast_kb:
        idx = fast_index
        meta_list = fast_metadata
    else:
        idx = index
        meta_list = metadata

    query_emb = embedder.encode([query], normalize_embeddings=True).astype("float32")
    similarities, indices = idx.search(query_emb, top_k * 2)  # Get more initially for filtering

    user_symptoms = extract_symptoms_from_text(query)
    retrieved = []

    for idx_i, faiss_score in zip(indices[0], similarities[0]):
        if idx_i >= len(meta_list):
            continue

        meta = meta_list[idx_i]
        disease_symptoms = safe_extract_symptoms(meta)
        
        overlap = symptom_overlap_score(user_symptoms, disease_symptoms)
        prevalence_score = map_prevalence(meta.get("prevalence"))
        
        # Get age risk score based on user's age group
        age_risk_score = meta.get(f"{user_age_group}_risk_score", -1)
        
        # Combined score with age risk weighting
        combined = (0.5 * faiss_score) + (0.3 * overlap) + (0.2 * max(age_risk_score, 0))

        retrieved.append({
            "name": meta.get("name", "Unknown"),
            "symptoms": disease_symptoms,
            "faiss_score": float(faiss_score),
            "overlap_score": overlap,
            "prevalence_score": prevalence_score,
            "age_risk_score": age_risk_score,
            "combined_score": combined,
            "prevalence": meta.get("prevalence", "Unknown"),
            "risk_factors_age": meta.get("risk_factors_age", {}),
            "formatted_text": meta.get("formatted_text", "")
        })

    # Sort by combined score (which includes age risk)
    retrieved = sorted(retrieved, key=lambda x: x["combined_score"], reverse=True)

    # Alternative: Sort by combined_score then age_risk_score
    # retrieved = sorted(retrieved, 
    #                   key=lambda x: (x["combined_score"], x["age_risk_score"]), 
    #                   reverse=True)

    if use_fast_kb and len(retrieved) < top_k:
        extra_needed = top_k - len(retrieved)
        extra = retrieve_conditions_faiss(query, top_k=extra_needed, use_fast_kb=False, user_age_group=user_age_group)
        retrieved.extend(extra)

    return retrieved[:top_k]

# -----------------------------
# TESTER
# -----------------------------
if __name__ == "__main__":
    print("\n=== 🔍 RAG TESTER ===")
    test_query = "fever, headache, sore throat"
    print("Query:", test_query)

    print("\n--- Fast KB Results ---")
    fast_results = retrieve_conditions_faiss(test_query, top_k=5, use_fast_kb=True)
    for r in fast_results:
        print(f"\n➡ {r['name']}")
        print("  Combined:", r["combined_score"])
        print("  Symptoms:", r["symptoms"])

    print("\n--- Full KB Results ---")
    full_results = retrieve_conditions_faiss(test_query, top_k=5, use_fast_kb=False)
    for r in full_results:
        print(f"\n➡ {r['name']}")
        print("  Combined:", r["combined_score"])
        print("  Symptoms:", r["symptoms"])
    # Test with different age groups
    print("\n--- Young Patient Results ---")
    young_results = retrieve_conditions_faiss("fever, headache", top_k=5, user_age_group="young")
    for r in young_results:
        print(f"{r['name']} - Age Risk: {r['age_risk_score']}")

    print("\n--- Older Patient Results ---")
    old_results = retrieve_conditions_faiss("fever, headache", top_k=5, user_age_group="old")
    for r in old_results:
        print(f"{r['name']} - Age Risk: {r['age_risk_score']}")