import httpx
from openai import OpenAI
from .retrival import retrieve_conditions_faiss
import json,re

http_client = httpx.Client(verify=False) # Désactive la vérification du certificat TLS/SSL

client = OpenAI(
    api_key="sk-ada9945ddcda497c9a8c5c59e2428478",
    base_url="https://tokenfactory.esprit.tn/api",
    http_client=http_client
)

confidence_threshold = 0.95
max_turns = 10

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def extract_json(text):
    """Safely extract JSON from LLM output"""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return "{}"

def normalize_symptom(s):
    """Normalize symptom strings to avoid duplicates"""
    s = s.lower().strip()
    s = s.replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    synonyms = {
        "fever": "high temperature",
        "sudden high temperature": "high temperature",
        "feeling tired": "fatigue",
        "aches and pains": "body aches",
        "diarrhoea or tummy pain": "diarrhea",
        "diarrhea or tummy pain": "diarrhea"
    }
    return synonyms.get(s, s)

def normalize_answer(question, answer):
    """Convert user's free-text answer to structured symptom"""
    answer = answer.lower().strip()
    if answer in ["yes", "y"]:
        return f"{question} present"
    elif answer in ["no", "n"]:
        return f"{question} absent"
    elif answer in ["sometimes", "occasionally"]:
        return f"{question} intermittent"
    else:
        return answer

def retrieve_conditions_expanded(query, negative_diseases, user_age_group=None, top_k=10):
    """Retrieve more RAG documents and filter out ruled-out diseases"""
    if user_age_group is None:
        user_age_group = "adult"  # Default age group
    
    print(f"Retrieving conditions with top_k={top_k}, age_group={user_age_group}")
    rag_docs = retrieve_conditions_faiss(query, top_k=top_k, user_age_group=user_age_group)
    print(f"Retrieved {len(rag_docs)} documents from FAISS")
    
    filtered_docs = []
    negative_diseases_lower = [d.lower() for d in negative_diseases] if negative_diseases else []
    
    for doc in rag_docs[:top_k]:  # Take more documents
        # Check both "name" and "disease" keys
        doc_name = doc.get("name", doc.get("disease", "")).lower()
        if doc_name and doc_name not in negative_diseases_lower:
            filtered_docs.append(doc)
    
    print(f"After filtering: {len(filtered_docs)} documents")
    return filtered_docs

def get_all_canonical_symptoms(diagnoses):
    """Extract all canonical symptoms from multiple diagnoses"""
    all_symptoms = set()
    for diagnosis in diagnoses:
        for symptom in diagnosis.get("canonical_symptoms", []):
            all_symptoms.add(normalize_symptom(symptom))
    return all_symptoms

def determine_age_group(age_input):
    """Convert age input to age group for medical context"""
    try:
        age = int(age_input)
        if age <= 18:
            return "young"
        elif age < 45:
            return "adult"
        else:
            return "old"
    except:
        # Handle text inputs
        age_lower = age_input.lower()
        if "child" in age_lower or "teen" in age_lower or "young" in age_lower:
            return "young"
        elif "adult" in age_lower or "middle" in age_lower:
            return "adult"
        elif "old" in age_lower or "senior" in age_lower or "elderly" in age_lower:
            return "old"
        else:
            return "adult"  # default

# -----------------------------
# LLM FUNCTIONS
# -----------------------------
def generate_diagnosis(positive_symptoms, negative_symptoms, negative_diseases, user_age_group=None, expand_search=False):
    # Check if we have symptoms
    if not positive_symptoms or len(positive_symptoms) == 0:
        print("Warning: No positive symptoms provided")
        return {"diagnoses": []}
    
    # Retrieve more conditions if we need to expand search
    top_k = 15 if expand_search else 10
    query_text = " ".join(positive_symptoms) if isinstance(positive_symptoms, list) else str(positive_symptoms)
    
    print(f"Retrieving RAG context for: {query_text}")
    rag_context = retrieve_conditions_expanded(query_text, negative_diseases, user_age_group, top_k)
    print(f"RAG context retrieved: {len(rag_context)} documents")
    
    if len(rag_context) == 0:
        print("Warning: No RAG context retrieved")

    age_context = ""
    if user_age_group:
        age_context = f"\nPatient age group: {user_age_group}. Consider conditions more common in this age group but do not completely rule out other conditions."

    # Format RAG context nicely
    rag_text = ""
    if rag_context and len(rag_context) > 0:
        rag_text = "\nRelevant medical conditions:\n"
        for i, doc in enumerate(rag_context[:5], 1):
            name = doc.get("name", "Unknown")
            symptoms = doc.get("symptoms", [])
            rag_text += f"{i}. {name}"
            if symptoms:
                rag_text += f" (symptoms: {', '.join(symptoms[:3])})"
            rag_text += "\n"
    else:
        rag_text = "\nNote: No specific medical knowledge retrieved. Use general medical knowledge.\n"

    diagnosis_prompt = f"""You are a medical assistant helping to diagnose patients.

Patient positive symptoms: {positive_symptoms}
Patient absent symptoms: {negative_symptoms}
Diseases ruled out: {list(negative_diseases) if negative_diseases else "None"}{age_context}
{rag_text}

Task:
- Identify top 3-5 likely diagnoses based on the symptoms.
- {"Consider less common conditions as well." if expand_search else "Focus on common conditions first."}
- Use positive and negative symptoms to adjust confidence scores (0.0 to 1.0).
- Consider age relevance but DO NOT fully eliminate conditions just because they're less common in the patient's age group.
- ALWAYS return at least 2-3 diagnoses, even if confidence is low (0.3-0.6).

CRITICAL: You MUST return valid JSON with at least 2 diagnoses. Do not return empty list.

Output JSON ONLY in this exact format:
{{
  "diagnoses": [
    {{
      "name": "Condition Name",
      "confidence": 0.75,
      "explanation": "Brief explanation why this condition matches the symptoms",
      "canonical_symptoms": ["symptom1", "symptom2"],
      "age_relevance": "high"
    }},
    {{
      "name": "Another Condition",
      "confidence": 0.65,
      "explanation": "Brief explanation",
      "canonical_symptoms": ["symptom1", "symptom3"],
      "age_relevance": "medium"
    }}
  ]
}}
"""
    response = client.chat.completions.create(
        model="hosted_vllm/Llama-3.1-70B-Instruct",
        messages=[
            {"role": "system", "content": "You are a medical assistant."},
            {"role": "user", "content": diagnosis_prompt}
        ],
        temperature=0.7,
        max_tokens=600,
        top_p=0.9
    )

    raw_response = response.choices[0].message.content
    print(f"LLM raw response (first 500 chars): {raw_response[:500]}")
    
    try:
        json_str = extract_json(raw_response)
        print(f"Extracted JSON (first 500 chars): {json_str[:500]}")
        result = json.loads(json_str)
        
        # Ensure we have diagnoses
        if not isinstance(result, dict):
            print(f"Error: LLM returned non-dict: {type(result)}")
            return {"diagnoses": []}
        
        if "diagnoses" not in result:
            print(f"Error: Missing 'diagnoses' key. Keys: {list(result.keys())}")
            return {"diagnoses": []}
        
        if not isinstance(result["diagnoses"], list) or len(result["diagnoses"]) == 0:
            print(f"Warning: Empty diagnoses list. Full result: {result}")
            return {"diagnoses": []}
        
        print(f"Successfully parsed {len(result['diagnoses'])} diagnoses")
        return result
        
    except json.JSONDecodeError as e:
        print(f"Error decoding diagnosis JSON: {e}")
        print(f"Raw response: {raw_response}")
        return {"diagnoses": []}
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return {"diagnoses": []}

def generate_missing_symptom_questions(diagnoses, asked_symptoms, user_age_group=None, max_questions=5):
    """Generate questions for missing canonical symptoms across multiple diagnoses"""
    questions = []
    
    # Get all canonical symptoms from top diagnoses
    all_canonical_symptoms = get_all_canonical_symptoms(diagnoses)
    
    # Generate questions for symptoms not yet asked
    for symptom in all_canonical_symptoms:
        if symptom not in asked_symptoms and len(questions) < max_questions:
            # Convert normalized symptom back to natural language question
            question_text = f"Do you have {symptom}?"
            questions.append(question_text)
            asked_symptoms.add(symptom)
    
    return questions

def generate_age_specific_questions(diagnoses, user_age_group, asked_symptoms):
    """Generate age-specific questions to refine diagnosis"""
    if not user_age_group:
        return []
    
    age_prompt = f"""
Based on these potential diagnoses: {[d['name'] for d in diagnoses[:3]]}
And the patient's age group: {user_age_group}

Generate 2-3 specific medical questions that are particularly relevant for this age group to help differentiate between conditions.

Focus on:
- Symptoms that manifest differently in {user_age_group} patients
- Age-specific risk factors
- Developmental or age-related considerations

Return as a JSON list of questions:
["question1", "question2", ...]
"""
    
    response = client.chat.completions.create(
        model="hosted_vllm/Llama-3.1-70B-Instruct",
        messages=[
            {"role": "system", "content": "You are a medical assistant."},
            {"role": "user", "content": age_prompt}
        ],
        temperature=0.7,
        max_tokens=300,
        top_p=0.9
    )
    
    try:
        questions_data = json.loads(extract_json(response.choices[0].message.content))
        questions = []
        for q in questions_data:
            if isinstance(q, str) and normalize_symptom(q) not in asked_symptoms:
                questions.append(q)
                asked_symptoms.add(normalize_symptom(q))
        return questions[:3]
    except:
        # Fallback age-specific questions
        fallback_questions = {
            "young": [
                "Has there been any recent exposure to sick children at school or daycare?",
                "Are there any developmental concerns or changes in behavior?",
                "Has the child been eating and drinking normally?"
            ],
            "adult": [
                "Have there been any recent work-related exposures or stressors?",
                "Are you taking any regular medications?",
                "Has there been any recent travel?"
            ],
            "old": [
                "Have you noticed any changes in memory or cognitive function?",
                "Are you taking multiple medications regularly?",
                "Have there been any recent falls or balance issues?"
            ]
        }
        return [q for q in fallback_questions.get(user_age_group, []) if normalize_symptom(q) not in asked_symptoms][:2]

def generate_general_medical_questions(positive_symptoms, asked_symptoms, max_questions=3):
    """Generate general medical questions when specific symptoms are exhausted"""
    general_prompt = f"""
Based on these symptoms: {positive_symptoms}
Generate {max_questions} general medical questions that could help differentiate between possible conditions.
Focus on questions about:
- Duration and timing of symptoms
- Severity and progression  
- Related bodily systems
- Potential triggers or exposures
- Associated symptoms commonly seen with these presentations

Return as a JSON list of questions:
["question1", "question2", ...]
"""
    
    response = client.chat.completions.create(
        model="hosted_vllm/Llama-3.1-70B-Instruct",
        messages=[
            {"role": "system", "content": "You are a medical assistant."},
            {"role": "user", "content": general_prompt}
        ],
        temperature=0.7,
        max_tokens=300,
        top_p=0.9
    )
    
    try:
        questions_data = json.loads(extract_json(response.choices[0].message.content))
        questions = []
        for q in questions_data:
            if isinstance(q, str) and q not in asked_symptoms:
                questions.append(q)
                asked_symptoms.add(normalize_symptom(q))
        return questions[:max_questions]
    except:
        # Fallback questions
        fallback_questions = [
            "How long have you had these symptoms?",
            "Have the symptoms been getting worse, better, or staying the same?",
            "Are there any factors that make your symptoms better or worse?"
        ]
        return [q for q in fallback_questions if normalize_symptom(q) not in asked_symptoms][:max_questions]

# -----------------------------
# MAIN LOOP (only runs when script is executed directly)
# -----------------------------
if __name__ == "__main__":
    user_input = input("Enter your symptoms (comma-separated): ")

    # Split input into individual symptoms
    input_symptoms = [normalize_symptom(s) for s in re.split(r",|\n", user_input) if s.strip()]

    positive_symptoms = input_symptoms.copy()
    negative_symptoms = []
    negative_diseases = set()
    asked_symptoms = set(input_symptoms)
    expand_search = False  # Flag to expand disease search
    user_age_group = None  # Will be set after age question

    previous_conf = {}

    # Ask age question first
    age_answer = input("To help with diagnosis, could you tell me your age or age group? ")
    user_age_group = determine_age_group(age_answer)
    print(f"✓ Noted: Patient age group: {user_age_group}")

    for turn in range(max_turns):
        # Step 1: Generate diagnosis (expand search if needed)
        diagnosis_data = generate_diagnosis(positive_symptoms, negative_symptoms, negative_diseases, user_age_group, expand_search)
        if not diagnosis_data:
            print("Failed to generate diagnosis. Stopping.")
            break

        print(f"\n--- Turn {turn+1} ---")
        print("Current diagnosis:", json.dumps(diagnosis_data, indent=2))

        # Step 2: Adjust confidence based on absent symptoms and age relevance
        for diagnosis in diagnosis_data["diagnoses"]:
            name = diagnosis["name"]
            prev_conf = previous_conf.get(name, diagnosis["confidence"])
            
            # Count present and absent symptoms
            num_present = sum(1 for s in positive_symptoms if normalize_symptom(s) in [normalize_symptom(cs) for cs in diagnosis["canonical_symptoms"]])
            num_absent = sum(1 for s in negative_symptoms if normalize_symptom(s) in [normalize_symptom(cs) for cs in diagnosis["canonical_symptoms"]])
            
            # Age relevance adjustment
            age_relevance = diagnosis.get("age_relevance", "medium")
            age_bonus = {
                "high": 0.03,
                "medium": 0.0, 
                "low": -0.02
            }.get(age_relevance, 0.0)
            
            # High coverage reward (your suggestion)
            expected_symptoms = len(diagnosis["canonical_symptoms"])
            coverage_bonus = 0.0
            if expected_symptoms > 0:
                coverage_ratio = num_present / expected_symptoms
                if coverage_ratio >= 0.9:
                    coverage_bonus = 0.12
                elif coverage_ratio >= 0.75:
                    coverage_bonus = 0.07
                elif coverage_ratio >= 0.6:
                    coverage_bonus = 0.03
            
            # Combined confidence calculation
            diagnosis["confidence"] = max(0, min(1,
                prev_conf 
                - 0.03 * num_absent      # Reduced penalty
                + age_bonus
                + coverage_bonus          # High coverage reward
            ))
            
            previous_conf[name] = diagnosis["confidence"]

        # Step 3: Check top confidence
        top_conf = max(d["confidence"] for d in diagnosis_data["diagnoses"])
        if top_conf >= confidence_threshold:
            print(f"\nDiagnosis confidence ({top_conf:.2f}) reached threshold. Stopping.")
            break

        # Step 4: Generate questions
        top_diagnoses = diagnosis_data["diagnoses"][:5]  # Consider more diagnoses
        
        questions = []
        
        # First: Try age-specific questions if we have age information
        if user_age_group and turn < 2:  # Ask age-specific questions early
            age_questions = generate_age_specific_questions(top_diagnoses, user_age_group, asked_symptoms)
            questions.extend(age_questions)
        
        # Second: Specific symptom questions
        if len(questions) < 3:
            symptom_questions = generate_missing_symptom_questions(top_diagnoses, asked_symptoms, user_age_group, max_questions=3)
            questions.extend(symptom_questions)
        
        # Third: If no specific questions, try general medical questions
        if not questions:
            print("No specific symptom questions available. Generating general medical questions...")
            questions = generate_general_medical_questions(positive_symptoms, asked_symptoms, max_questions=3)
            expand_search = True  # Expand search in next iteration
        
        # Fourth: If still no questions, consider ruling out low-confidence diagnoses
        if not questions and len(diagnosis_data["diagnoses"]) > 1:
            lowest_conf_diagnosis = min(diagnosis_data["diagnoses"], key=lambda x: x["confidence"])
            negative_diseases.add(lowest_conf_diagnosis["name"])
            print(f"Ruling out low-confidence diagnosis: {lowest_conf_diagnosis['name']}")
            continue

        if not questions:
            print("\nNo more questions available. Stopping.")
            break

        # Step 5: Ask questions
        print(f"\nAsking {len(questions)} question(s):")
        for question in questions:
            answer = input(f"{question} ")
            normalized = normalize_answer(question.replace("Do you have ", "").replace("?", ""), answer)

            if "present" in normalized or "intermittent" in normalized:
                symptom = normalized.replace(" present", "").replace(" intermittent", "")
                positive_symptoms.append(symptom)
                print(f"✓ Added positive symptom: {symptom}")
            elif "absent" in normalized:
                symptom = normalized.replace(" absent", "")
                negative_symptoms.append(symptom)
                print(f"✗ Added negative symptom: {symptom}")
            else:
                # For general questions or free-text answers
                positive_symptoms.append(normalized)
                print(f"ℹ Added symptom information: {normalized}")

    # -----------------------------
    # FINAL DIAGNOSIS
    # -----------------------------
    print("\n" + "="*50)
    print("FINAL DIAGNOSIS")
    print("="*50)
    if diagnosis_data:
        # Sort diagnoses by confidence
        diagnosis_data["diagnoses"].sort(key=lambda x: x["confidence"], reverse=True)
        print(json.dumps(diagnosis_data, indent=2))
        
        # Print summary with age context
        top_diagnosis = diagnosis_data["diagnoses"][0]
        print(f"\nTOP DIAGNOSIS: {top_diagnosis['name']} (confidence: {top_diagnosis['confidence']:.2f})")
        print(f"Explanation: {top_diagnosis['explanation']}")
        if user_age_group:
            print(f"Age relevance: {top_diagnosis.get('age_relevance', 'medium')} for {user_age_group} patients")
    else:
        print("No diagnosis could be determined.")