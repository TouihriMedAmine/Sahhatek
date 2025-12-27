import json
from sentence_transformers import SentenceTransformer
import faiss
import pickle

# Load full NHS conditions JSON
with open('nhs_conditions2.json', 'r') as f:
    conditions_data = json.load(f)

# -----------------------------
# Step 1: Determine frequent conditions automatically
prevalence_order = {
    "very common": 4,
    "common": 3,
    "uncommon": 2,
    "rare": 1,
    "very rare": 0
}

def map_prevalence(value):
    if not value:            # handles None or empty string
        return -1            # unknown prevalence -> lowest rank
    v = value.lower().strip()
    for key in prevalence_order:
        if v.startswith(key):
            return prevalence_order[key]
    return -1

# -----------------------------
# Age risk scoring function
def calculate_age_risk_score(risk_factors, target_age_group="young"):
    """
    Calculate age risk score for sorting
    Returns: 2 (high risk), 1 (moderate risk), 0 (no specific risk), -1 (unknown)
    """
    if not risk_factors or not isinstance(risk_factors, dict):
        return -1  # unknown
    
    if target_age_group == "young":
        if risk_factors.get("young") and risk_factors.get("old"):
            return 1  # affects both, but young included
        elif risk_factors.get("young"):
            return 2  # specifically affects young
        elif risk_factors.get("old"):
            return 0  # only affects old
        else:
            return -1  # unknown
    else:  # target_age_group == "old"
        if risk_factors.get("young") and risk_factors.get("old"):
            return 1  # affects both, but old included
        elif risk_factors.get("old"):
            return 2  # specifically affects old
        elif risk_factors.get("young"):
            return 0  # only affects young
        else:
            return -1  # unknown

# -----------------------------
# Sort conditions by prevalence (descending) and pick top N
conditions_sorted = sorted(
    conditions_data,
    key=lambda c: map_prevalence(c.get("prevalence")),
    reverse=True
)

fast_conditions = conditions_sorted[:25]
full_conditions = conditions_data

# -----------------------------
# Step 2: Format condition text
# -----------------------------
def format_condition_text(condition):
    text_parts = [
        f"Condition: {condition.get('name', 'Unknown')}",
        f"Severity: {condition.get('severity', 'Unknown')}",
        f"Prevalence: {condition.get('prevalence', 'Unknown')}",
        f"Age Severity: {condition.get('age_severity', 'Unknown')}",
    ]

    # Symptoms
    symptoms = condition.get('symptoms') or []
    if isinstance(symptoms, list) and symptoms:
        text_parts.append(f"Symptoms: {', '.join(symptoms)}")

    # Treatment
    treatment = condition.get('treatment') or []
    if isinstance(treatment, list) and treatment:
        text_parts.append(f"Treatment: {', '.join(treatment)}")

    # Risk factors (optional)
    risk_factors = condition.get('risk_factors_age') or {}
    risk_text_parts = []
    if risk_factors.get('young', False):
        risk_text_parts.append("higher risk for young people")
    if risk_factors.get('old', False):
        risk_text_parts.append("higher risk for older people")
    if risk_text_parts:
        text_parts.append(f"Risk Factors: {', '.join(risk_text_parts)}")

    return ". ".join(text_parts)

# Create formatted texts
fast_texts = [format_condition_text(c) for c in fast_conditions]
full_texts = [format_condition_text(c) for c in full_conditions]

# -----------------------------
# Step 3: Generate embeddings
# -----------------------------
embedder = SentenceTransformer('all-MiniLM-L6-v2')
fast_embeddings = embedder.encode(fast_texts, normalize_embeddings=True)
full_embeddings = embedder.encode(full_texts, normalize_embeddings=True)

# -----------------------------
# Step 4: Create FAISS indices
# -----------------------------
dimension = fast_embeddings.shape[1]

fast_index = faiss.IndexFlatIP(dimension)
fast_index.add(fast_embeddings.astype('float32'))

full_index = faiss.IndexFlatIP(dimension)
full_index.add(full_embeddings.astype('float32'))

# -----------------------------
# Step 5: Save metadata WITH SYMPTOMS AND AGE RISK FACTORS
# -----------------------------
# Store ALL original data including symptoms and age risk factors
fast_metadata = [{
    "id": i, 
    "name": c['name'], 
    "formatted_text": fast_texts[i],
    "symptoms": c.get('symptoms', []),  # Store original symptoms
    "prevalence": c.get('prevalence'),  # Store prevalence for sorting
    "risk_factors_age": c.get('risk_factors_age', {}),  # Store age risk factors
    "young_risk_score": calculate_age_risk_score(c.get('risk_factors_age'), "young"),
    "old_risk_score": calculate_age_risk_score(c.get('risk_factors_age'), "old"),
    "original_data": c  # Store complete original data
} for i, c in enumerate(fast_conditions)]

full_metadata = [{
    "id": i, 
    "name": c['name'], 
    "formatted_text": full_texts[i],
    "symptoms": c.get('symptoms', []),  # Store original symptoms
    "prevalence": c.get('prevalence'),  # Store prevalence for sorting
    "risk_factors_age": c.get('risk_factors_age', {}),  # Store age risk factors
    "young_risk_score": calculate_age_risk_score(c.get('risk_factors_age'), "young"),
    "old_risk_score": calculate_age_risk_score(c.get('risk_factors_age'), "old"),
    "original_data": c  # Store complete original data
} for i, c in enumerate(full_conditions)]

with open("fast_medical_metadata.pkl", "wb") as f:
    pickle.dump(fast_metadata, f)

with open("full_medical_metadata.pkl", "wb") as f:
    pickle.dump(full_metadata, f)

faiss.write_index(fast_index, "fast_medical_index.faiss")
faiss.write_index(full_index, "full_medical_index.faiss")

print(f"Fast KB created with top 25 prevalent conditions ({fast_index.ntotal} vectors)")
print(f"Full KB created with all conditions ({full_index.ntotal} vectors)")

# Print some examples to verify age risk scoring
print("\n=== Age Risk Scoring Examples ===")
sample_conditions = [
    {"name": "Reactive arthritis", "risk_factors_age": {"young": False, "old": True}},
    {"name": "Condition affecting young", "risk_factors_age": {"young": True, "old": False}},
    {"name": "Condition affecting both", "risk_factors_age": {"young": True, "old": True}},
    {"name": "Condition with no risk data", "risk_factors_age": {}},
]

for condition in sample_conditions:
    young_score = calculate_age_risk_score(condition.get('risk_factors_age'), "young")
    old_score = calculate_age_risk_score(condition.get('risk_factors_age'), "old")
    print(f"{condition['name']}: Young risk = {young_score}, Old risk = {old_score}")