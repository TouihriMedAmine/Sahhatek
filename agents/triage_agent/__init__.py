"""
Triage Agent Module - Integrates triage/logic.py into LangGraph with Knowledge Base
"""

from .agent import (
    triage_agent,
    extract_symptoms,
    start_diagnosis,
    generate_diagnosis,
    recommend_care,
    answer_triage_question,
    TriageAgentState,
    DiagnosisResult
)

from .knowledge_base import (
    get_knowledge_base,
    TriageKnowledgeBase,
    KnowledgeDocument,
    RetrievalResult
)

__all__ = [
    "triage_agent",
    "extract_symptoms",
    "start_diagnosis",
    "generate_diagnosis",
    "recommend_care",
    "answer_triage_question",
    "TriageAgentState",
    "DiagnosisResult",
    "get_knowledge_base",
    "TriageKnowledgeBase",
    "KnowledgeDocument",
    "RetrievalResult"
]
