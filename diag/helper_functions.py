import json
import re

def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else "{}"


def normalize_symptom(s):
    s = s.lower().strip().replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    synonyms = {
        "fever": "high temperature",
        "sudden high temperature": "high temperature",
        "feeling tired": "fatigue",
        "aches and pains": "body aches",
        "diarrhoea or tummy pain": "diarrhea",
    }
    return synonyms.get(s, s)


def normalize_answer(question, answer):
    answer = answer.lower().strip()
    if answer in ["yes", "y"]:
        return f"{question} present"
    if answer in ["no", "n"]:
        return f"{question} absent"
    return answer


def determine_age_group(age_input):
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

def get_all_canonical_symptoms(diagnoses):
    """
    Extract all canonical symptoms from multiple diagnoses.

    Args:
        diagnoses (list[dict]): List of diagnosis dicts. Each dict has a 'canonical_symptoms' key.

    Returns:
        set[str]: Set of normalized symptom strings.
    """
    all_symptoms = set()
    for diagnosis in diagnoses:
        for symptom in diagnosis.get("canonical_symptoms", []):
            all_symptoms.add(normalize_symptom(symptom))
    return all_symptoms

def generate_missing_symptom_questions(diagnoses, asked_symptoms, max_questions=5):
    questions = []
    all_canonical_symptoms = get_all_canonical_symptoms(diagnoses)

    for symptom in all_canonical_symptoms:
        symptom = normalize_symptom(symptom)
        if symptom not in asked_symptoms and len(questions) < max_questions:
            questions.append(f"Do you have {symptom}?")

    return questions

