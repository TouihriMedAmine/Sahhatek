AGENT_REGISTRY = {
    "medical_qa": {
        "role": "Medical Question Answering",
        "can_handle": [
            "medical questions",
            "disease explanations",
            "medication information",
            "general health advice"
        ],
        "should_delegate_when": [
            "symptoms are present",
            "emergency indicators appear",
            "mental distress detected",
            "misinformation suspected"
        ],
        "can_delegate_to": ["triage", "mental_health", "rumor"]
    },

    "triage": {
        "role": "Medical Triage & Guidance",
        "can_handle": [
            "symptom assessment",
            "urgency classification",
            "care guidance"
        ],
        "should_delegate_when": [
            "mental health crisis",
            "misinformation detected"
        ],
        "can_delegate_to": ["mental_health", "rumor"]
    },

    "mental_health": {
        "role": "Mental Health Support",
        "can_handle": [
            "emotional distress",
            "anxiety",
            "crisis intervention"
        ],
        "can_delegate_to": []
    },

    "rumor": {
        "role": "Medical Misinformation Detection",
        "can_handle": [
            "false medical claims",
            "dangerous advice",
            "social media rumors"
        ],
        "can_delegate_to": []
    }
}
