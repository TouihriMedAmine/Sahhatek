import json
import re
import httpx
from typing import TypedDict, List, Set, Optional,Dict
from openai import OpenAI
from helper_functions import *
from retrival import retrieve_conditions_faiss
from langgraph.graph import StateGraph, END
from langchain.tools import tool

# Create HTTP client with proper SSL verification
http_client = httpx.Client(verify=False)

client = OpenAI(
    api_key="sk-ada9945ddcda497c9a8c5c59e2428478",
    base_url="https://tokenfactory.esprit.tn/api",
    http_client=http_client
)

CONFIDENCE_THRESHOLD = 0.97
MAX_TURNS = 10

class DiagnosisState(TypedDict):
    positive_symptoms: List[str]
    negative_symptoms: List[str]
    asked_symptoms: List[str]
    asked_questions: List[str]
    diagnoses: List[dict]
    user_age_group: str
    max_confidence: float
    turn: int
    retrieved_conditions: List[dict]
    confidence_history: Dict[str, List[float]]


@tool
def access_knowledgebase(symptoms: List[str], age_group: str, expand: bool = True) -> List[dict]:
    """Retrieve medical conditions from FAISS"""
    top_k = 15 if expand else 10
    conditions = retrieve_conditions_faiss(
        " ".join(symptoms),
        user_age_group=age_group
    )
    return conditions[:top_k] if conditions else []
def debug_symptom_check(state: DiagnosisState):
    """Debug function to check symptoms vs asked symptoms"""
    if not state.get("diagnoses"):
        print("No diagnoses to debug.")
        return
    
    top_3 = state["diagnoses"][:3]
    asked_set = set(state["asked_symptoms"])
    
    print(f"\n{'='*60}")
    print("DEBUG: SYMPTOM CHECK")
    print("="*60)
    
    for i, diagnosis in enumerate(top_3):
        print(f"\n{i+1}. {diagnosis['name']} ({diagnosis.get('confidence', 0.0):.1%})")
        
        if "canonical_symptoms" in diagnosis:
            canonical_symptoms = diagnosis.get("canonical_symptoms", [])
            print(f"   Total canonical symptoms: {len(canonical_symptoms)}")
            
            asked_count = 0
            unasked_symptoms = []
            
            for symptom in canonical_symptoms:
                if isinstance(symptom, str):
                    normalized = normalize_symptom(symptom)
                    is_asked = normalized in asked_set
                    
                    if is_asked:
                        asked_count += 1
                    else:
                        unasked_symptoms.append(symptom)
                    
                    status = "✓" if is_asked else "✗"
                    print(f"   {status} {symptom}")
            
            print(f"   Asked: {asked_count}/{len(canonical_symptoms)} symptoms")
            
            if unasked_symptoms:
                print(f"   Unasked symptoms: {', '.join(unasked_symptoms[:5])}")
                if len(unasked_symptoms) > 5:
                    print(f"     ... and {len(unasked_symptoms)-5} more")
            else:
                print("   ✓ All symptoms have been asked about")
    
    print(f"\nTotal asked symptoms: {len(asked_set)}")
    print("Sample of asked symptoms:")
    for i, symptom in enumerate(list(asked_set)[:10]):
        print(f"  {i+1}. {symptom}")
    
    print("="*60)
def calculate_diagnosis_confidence(
    diagnosis: dict,
    positive_symptoms: List[str],
    negative_symptoms: List[str],
    age_group: str,
    previous_confidence: Dict[str, float]
) -> float:
    """Calculate confidence using your exact formula"""
    name = diagnosis["name"]
    prev_conf = previous_confidence.get(name, diagnosis.get("confidence", 0.5))
    
    # Count present and absent symptoms
    canonical_symptoms = diagnosis.get("canonical_symptoms", [])
    
    # Normalize all symptoms for comparison
    normalized_canonical = [normalize_symptom(cs) for cs in canonical_symptoms]
    normalized_positive = [normalize_symptom(ps) for ps in positive_symptoms]
    normalized_negative = [normalize_symptom(ns) for ns in negative_symptoms]
    
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
    
    # Age relevance adjustment (you can enhance this based on age_group)
    # For now, using medium as default
    age_relevance = diagnosis.get("age_relevance", "medium")
    age_bonus = {
        "high": 0.03,
        "medium": 0.0, 
        "low": -0.02
    }.get(age_relevance, 0.0)
    
    # High coverage reward (your suggestion)
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
    
    # Combined confidence calculation (YOUR EXACT FORMULA)
    confidence = max(0, min(1,
        prev_conf 
        - 0.03 * num_absent      # Reduced penalty
        + age_bonus
        + coverage_bonus          # High coverage reward
    ))
    
    return confidence

def get_all_symptoms_from_conditions(conditions: List[dict]) -> Set[str]:
    """Extract ALL unique symptoms from retrieved conditions"""
    all_symptoms = set()
    for condition in conditions:
        symptoms = condition.get("symptoms", [])
        # Ensure all symptoms are strings and normalized
        for symptom in symptoms:
            if isinstance(symptom, str):
                normalized = normalize_symptom(symptom)
                all_symptoms.add(normalized)
    return all_symptoms

def generate_questions_from_diagnoses(top_diagnoses: List[dict], 
                                    already_asked: Set[str]) -> List[str]:
    """Generate questions about symptoms from top diagnoses"""
    questions = []
    
    # Extract symptoms from top diagnoses (prioritizing highest confidence)
    for diagnosis in top_diagnoses:
        canonical_symptoms = diagnosis.get("canonical_symptoms", [])
        
        for symptom in canonical_symptoms:
            if isinstance(symptom, str):
                normalized = normalize_symptom(symptom)
                
                if normalized not in already_asked:
                    # Convert to question
                    symptom_text = normalized.replace('_', ' ').replace('-', ' ')
                    question = f"Do you have {symptom_text}?"
                    
                    if question not in questions:
                        questions.append(question)
                        
                    # Limit total questions
                    if len(questions) >= 5:
                        return questions
    
    return questions

def llm_diagnose(state: DiagnosisState) -> DiagnosisState:
    """LLM evaluates retrieved conditions and provides diagnoses"""
    
    # Retrieve conditions
    conditions = access_knowledgebase.invoke({
        "symptoms": state["positive_symptoms"],
        "age_group": state["user_age_group"],
        "expand": state["turn"] > 2
    })
    
    state["retrieved_conditions"] = conditions
    
    if not conditions:
        print("\n⚠️ No conditions retrieved from knowledge base.")
        state["diagnoses"] = []
        state["max_confidence"] = 0.0
        return state
    
    # Store previous confidences for tracking
    previous_conf = {}
    if state.get("diagnoses"):
        for d in state["diagnoses"]:
            previous_conf[d["name"]] = d.get("confidence", 0.5)
    
    # Prepare conditions for LLM to evaluate
    conditions_summary = []
    for i, cond in enumerate(conditions[:15]):  # Top 15 for evaluation
        name = cond.get("name", "Unknown")
        symptoms = cond.get("symptoms", [])
        
        conditions_summary.append({
            "id": i + 1,
            "name": name,
            "canonical_symptoms": symptoms[:8],  # First 8 symptoms
            "total_symptoms": len(symptoms)
        })
    
    # Prompt LLM to select top candidates (NOT assign confidence)
    prompt = f"""You are a medical diagnosis selector. Your task is to identify the most relevant conditions.

PATIENT INFORMATION:
- Age group: {state['user_age_group']}
- Confirmed symptoms: {state['positive_symptoms']}
- Absent symptoms: {state['negative_symptoms']}

CONDITIONS FROM DATABASE:
{json.dumps(conditions_summary, indent=2)}

YOUR TASK:
Select the 3-5 most relevant conditions from the list above.
Return ONLY JSON with the selected conditions.

CRITICAL:
1. Select ONLY from the list above
2. Return 3-5 conditions maximum
3. Include ALL canonical_symptoms exactly as shown
4. DO NOT assign confidence scores - just list the conditions
5. Sort by relevance (most relevant first)

JSON FORMAT:
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
        
        # Extract JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            data = json.loads(json_str)
            
            selected_conditions = data.get("selected_conditions", [])
            
            # Apply YOUR confidence formula to each selected condition
            diagnoses = []
            for condition in selected_conditions[:5]:  # Max 5
                # Find full condition info to get age_relevance if available
                full_condition = None
                for cond in conditions:
                    if cond.get("name") == condition["name"]:
                        full_condition = cond
                        break
                
                if full_condition:
                    # Get age_relevance from condition if available
                    age_relevance = full_condition.get("age_relevance", "medium")
                    
                    # Create diagnosis object
                    diagnosis = {
                        "name": condition["name"],
                        "canonical_symptoms": condition.get("canonical_symptoms", []),
                        "age_relevance": age_relevance,
                        "confidence": 0.5  # Initial confidence
                    }
                    
                    # Calculate confidence using YOUR formula
                    confidence = calculate_diagnosis_confidence(
                        diagnosis=diagnosis,
                        positive_symptoms=state["positive_symptoms"],
                        negative_symptoms=state["negative_symptoms"],
                        age_group=state["user_age_group"],
                        previous_confidence=previous_conf
                    )
                    
                    diagnosis["confidence"] = confidence
                    diagnoses.append(diagnosis)
            
            # Sort by confidence
            diagnoses.sort(key=lambda x: x["confidence"], reverse=True)
            state["diagnoses"] = diagnoses
            
            # Calculate max confidence
            if state["diagnoses"]:
                state["max_confidence"] = max(d.get("confidence", 0.0) for d in state["diagnoses"])
                print(f"\n✓ Generated {len(state['diagnoses'])} diagnoses with confidence:")
                for i, d in enumerate(state["diagnoses"][:3]):
                    print(f"  {i+1}. {d['name']}: {d['confidence']:.1%}")
            else:
                state["max_confidence"] = 0.0
                
        else:
            state["diagnoses"] = []
            state["max_confidence"] = 0.0
            
    except Exception as e:
        print(f"Error in LLM diagnosis: {e}")
        state["diagnoses"] = []
        state["max_confidence"] = 0.0

    return state

def ask_user(state: DiagnosisState) -> DiagnosisState:
    """Ask user about symptoms and update confidence"""
    
    if not state.get("diagnoses"):
        print("No diagnoses to generate questions from.")
        return state
    
    # Get top 3 diagnoses for question generation
    top_diagnoses = state["diagnoses"][:3]
    
    # Generate questions
    asked_set = set(state["asked_symptoms"])
    questions = generate_questions_from_diagnoses(top_diagnoses, asked_set)
    
    if not questions:
        print("\nNo new symptoms to ask about from top diagnoses.")
        return state
    
    print(f"\n{'='*50}")
    print(f"TURN {state['turn'] + 1}: Asking about symptoms from top {len(top_diagnoses)} diagnoses")
    print("="*50)
    
    # Store previous confidences for tracking
    previous_conf = {}
    for d in state["diagnoses"]:
        previous_conf[d["name"]] = d.get("confidence", 0.5)
    
    # Ask questions
    for q in questions:
        if q in state["asked_questions"]:
            continue
        
        state["asked_questions"].append(q)
        
        # Get user response
        while True:
            print(f"\n{q}")
            ans = input("Your answer (yes/no): ").lower().strip()
            if ans in ['yes', 'no', 'y', 'n', 'yes i do', 'no i dont']:
                break
            print("Please answer with 'yes' or 'no'")
        
        # Extract symptom
        symptom = normalize_symptom(
            q.replace("Do you have ", "")
             .replace("?", "")
             .strip()
        )
        
        if symptom not in state["asked_symptoms"]:
            state["asked_symptoms"].append(symptom)
        
        if ans in ['yes', 'y', 'yes i do']:
            state["positive_symptoms"].append(symptom)
            print(f"✓ Added: {symptom}")
        else:
            state["negative_symptoms"].append(symptom)
            print(f"✗ Not present: {symptom}")
    
    # AFTER asking questions, RECALCULATE all confidences using YOUR formula
    print("\n" + "-"*50)
    print("UPDATING CONFIDENCE SCORES...")
    print("-"*50)
    
    updated_diagnoses = []
    for diagnosis in state["diagnoses"]:
        # Recalculate confidence with updated symptoms
        confidence = calculate_diagnosis_confidence(
            diagnosis=diagnosis,
            positive_symptoms=state["positive_symptoms"],
            negative_symptoms=state["negative_symptoms"],
            age_group=state["user_age_group"],
            previous_confidence=previous_conf
        )
        
        diagnosis["confidence"] = confidence
        updated_diagnoses.append(diagnosis)
    
    # Sort by new confidence
    updated_diagnoses.sort(key=lambda x: x["confidence"], reverse=True)
    state["diagnoses"] = updated_diagnoses
    
    # Update max confidence
    if state["diagnoses"]:
        state["max_confidence"] = max(d.get("confidence", 0.0) for d in state["diagnoses"])
        print(f"\nUpdated top 3 diagnoses:")
        for i, d in enumerate(state["diagnoses"][:3]):
            print(f"  {i+1}. {d['name']}: {d['confidence']:.1%}")
            # Show confidence change if we have previous
            if d["name"] in previous_conf:
                change = d["confidence"] - previous_conf[d["name"]]
                if abs(change) > 0.001:
                    arrow = "↑" if change > 0 else "↓"
                    print(f"       ({arrow}{abs(change):.1%})")
    
    state["turn"] += 1
    return state

def should_continue(state: DiagnosisState) -> str:
    """Determine whether to continue asking questions"""
    
    # 1. High confidence reached in top diagnosis
    top_diagnosis = state["diagnoses"][0] if state.get("diagnoses") else None
    if top_diagnosis and top_diagnosis.get("confidence", 0.0) >= CONFIDENCE_THRESHOLD:
        print(f"\n{'='*50}")
        print(f"✓ HIGH CONFIDENCE REACHED in top diagnosis: {top_diagnosis.get('confidence', 0.0):.2%}")
        print(f"  Top diagnosis: {top_diagnosis.get('name', 'Unknown')}")
        print("="*50)
        return END
    
    # 2. Check if we can ask more questions from top 3 diagnoses
    if state.get("diagnoses"):
        top_3 = state["diagnoses"][:3]
        asked_set = set(state["asked_symptoms"])
        
        # Get all symptoms from top 3 diagnoses
        all_symptoms_top_3 = set()
        symptom_details = []  # Store for debugging
        for diagnosis in top_3:
            if "canonical_symptoms" in diagnosis:
                for symptom in diagnosis["canonical_symptoms"]:
                    if isinstance(symptom, str):
                        normalized = normalize_symptom(symptom)
                        all_symptoms_top_3.add(normalized)
                        symptom_details.append({
                            "diagnosis": diagnosis["name"],
                            "original": symptom,
                            "normalized": normalized
                        })
        
        remaining_symptoms = all_symptoms_top_3 - asked_set
        
        if not remaining_symptoms:
            # DEBUGGING: Print all canonical symptoms and asked symptoms
            print(f"\n{'='*50}")
            print("DEBUG: SYMPTOM ANALYSIS")
            print("="*50)
            print(f"Total unique symptoms in top 3 diagnoses: {len(all_symptoms_top_3)}")
            print(f"Total asked symptoms: {len(asked_set)}")
            print(f"Remaining symptoms to ask: {len(remaining_symptoms)}")
            print("\nAll canonical symptoms from top 3 diagnoses:")
            for detail in symptom_details:
                asked_status = "✓" if detail["normalized"] in asked_set else "✗"
                print(f"  {asked_status} {detail['diagnosis']}: {detail['original']} -> {detail['normalized']}")
            
            print("\nAlready asked symptoms:")
            for i, symptom in enumerate(list(asked_set)[:20]):  # Show first 20
                print(f"  {i+1}. {symptom}")
            
            print("\n" + "="*50)
            print("✓ ASKED ABOUT ALL SYMPTOMS FROM TOP 3 DIAGNOSES")
            print("Top 3 diagnoses:")
            for i, d in enumerate(top_3):
                print(f"  {i+1}. {d['name']} ({d.get('confidence', 0.0):.1%})")
            print("="*50)
            return END
    
    # 3. Maximum turns reached
    if state.get("turn", 0) >= MAX_TURNS:
        print(f"\n{'='*50}")
        print(f"✓ MAXIMUM TURNS REACHED ({MAX_TURNS})")
        print("="*50)
        return END
    
    # 4. No diagnoses or fewer than 3 diagnoses
    if not state.get("diagnoses") or len(state["diagnoses"]) < 1:
        print("\n⚠️ Insufficient diagnoses. Retrieving more conditions...")
        return "llm_diagnose"
    
    # Continue asking questions
    return "ask_user"

# Build the state graph
builder = StateGraph(DiagnosisState)

builder.add_node("llm_diagnose", llm_diagnose)
builder.add_node("ask_user", ask_user)

builder.set_entry_point("llm_diagnose")

builder.add_conditional_edges(
    "llm_diagnose",
    should_continue,
    {
        "ask_user": "ask_user",
        "llm_diagnose": "llm_diagnose",  # Allow retry if no diagnoses
        END: END
    }
)

builder.add_edge("ask_user", "llm_diagnose")

graph = builder.compile()

def main():
    """Main execution function"""
    print("="*60)
    print("MEDICAL DIAGNOSIS ASSISTANT")
    print("="*60)
    print("Note: LLM only evaluates retrieved conditions")
    print("Questions generated automatically from symptom database")
    print("="*60)
    
    # Get user input
    user_input = input("\nEnter your symptoms (comma-separated): ").strip()
    symptoms = [normalize_symptom(s.strip()) for s in user_input.split(",") if s.strip()]
    
    if not symptoms:
        print("No symptoms provided. Exiting.")
        return
    
    age_input = input("Enter your age or age group: ").strip()
    age_group = determine_age_group(age_input)
    
    # Create initial state
    initial_state = {
        "positive_symptoms": symptoms,
        "negative_symptoms": [],
        "asked_symptoms": symptoms[:],  # Initial symptoms are already "asked"
        "asked_questions": [],
        "diagnoses": [],
        "user_age_group": age_group,
        "max_confidence": 0.0,
        "turn": 0,
        "retrieved_conditions": []
    }
    
    print(f"\n{'='*50}")
    print(f"PATIENT PROFILE")
    print("="*50)
    print(f"Age group: {age_group}")
    print(f"Initial symptoms: {', '.join(symptoms)}")
    print("="*50)
    print("\nStarting diagnosis process...\n")
    
    # Run the diagnostic process
    try:
        final_state = graph.invoke(initial_state)
        
        # Display results
        print("\n" + "="*60)
        print("FINAL DIAGNOSIS")
        print("="*60)
        
        if final_state["diagnoses"]:
            # Sort by confidence
            final_state["diagnoses"].sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
            
            print("\nTOP DIAGNOSES (Disease, Age Severity):")
            print("-" * 60)
            
            # Get age severity mapping based on patient's age group
            age_severity_map = {
                "child": {"low": "Mild in children", "medium": "Moderate in children", "high": "Severe in children"},
                "young": {"low": "Mild in young adults", "medium": "Moderate in young adults", "high": "Severe in young adults"},
                "adult": {"low": "Mild in adults", "medium": "Moderate in adults", "high": "Severe in adults"},
                "old": {"low": "Mild in elderly", "medium": "Moderate in elderly", "high": "Severe in elderly"}
            }
            
            # Determine age severity for each diagnosis
            diagnoses_with_severity = []
            
            for i, diagnosis in enumerate(final_state["diagnoses"][:5], 1):  # Top 5
                name = diagnosis.get("name", "Unknown")
                confidence = diagnosis.get("confidence", 0.0) * 100
                
                # Determine age severity based on confidence
                if confidence >= 80:
                    severity_level = "high"
                elif confidence >= 60:
                    severity_level = "medium"
                else:
                    severity_level = "low"
                
                # Get age-specific severity description
                age_severity = age_severity_map.get(age_group, {}).get(severity_level, severity_level)
                
                # Format: Disease, Age Severity
                diagnosis_output = f"{name}, {age_severity}"
                diagnoses_with_severity.append(diagnosis_output)
                
                # Print detailed info
                print(f"\n{i}. {diagnosis_output}")
                print(f"   Confidence: {confidence:.1f}%")
                
                # Show matching symptoms
                if "canonical_symptoms" in diagnosis:
                    patient_symptoms_lower = [s.lower() for s in final_state["positive_symptoms"]]
                    matching = []
                    for symptom in diagnosis["canonical_symptoms"][:5]:
                        symptom_lower = symptom.lower()
                        for ps in patient_symptoms_lower:
                            if ps in symptom_lower or symptom_lower in ps:
                                matching.append(symptom)
                                break
                    
                    if matching:
                        print(f"   Matching symptoms: {', '.join(matching[:3])}")
            
            # Print comma-separated list for easy copying
            print("\n" + "="*60)
            print("FINAL OUTPUT (comma-separated):")
            print("="*60)
            print(", ".join(diagnoses_with_severity))
            
        else:
            print("\n⚠️ No diagnoses could be determined.")
            print("Possible reasons:")
            print("1. No matching conditions found in database")
            print("2. LLM failed to generate valid diagnoses")
            print("3. Insufficient symptom information")
        
        # Statistics
        print(f"\n{'='*50}")
        print("DIAGNOSIS STATISTICS")
        print("="*50)
        print(f"Total questions asked: {len(final_state['asked_questions'])}")
        print(f"Total symptoms considered: {len(final_state['asked_symptoms'])}")
        print(f"Positive symptoms: {len(final_state['positive_symptoms'])}")
        print(f"Negative symptoms: {len(final_state['negative_symptoms'])}")
        print(f"Total turns: {final_state['turn']}")
        print(f"Max confidence reached: {final_state['max_confidence']:.2%}")
        
        # Show what was retrieved
        if final_state.get("retrieved_conditions"):
            print(f"\nConditions retrieved: {len(final_state['retrieved_conditions'])}")
        
    except Exception as e:
        print(f"\n❌ An error occurred during diagnosis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()