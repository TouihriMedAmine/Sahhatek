# agents/mental_agent/service.py
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from groq import Groq

# 🎯 LangSmith Integration
from agents.langsmith_decorators import (
    trace_llm_call, trace_retrieval
)

# ---------------- CONFIG ----------------
PRIMARY_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
PLAN_TEMP = float(os.getenv("PLAN_TEMP", "0.7"))
ANALYSIS_TEMP = float(os.getenv("ANALYSIS_TEMP", "0.2"))
CHAT_TEMP = float(os.getenv("CHAT_TEMP", "0.8"))

# ✅ Turn ON in tests to avoid Chroma downloads/timeouts
TEST_MODE = os.getenv("TEST_MODE", "false").strip().lower() in ("1", "true", "yes", "y")

CHROMA_DIR = os.getenv(
    "CHROMA_DIR",
    os.path.join(os.path.dirname(__file__), "chroma_store"),
)
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "wellbeing_kb")

# ---------------- SAFETY / URGENCY DETECTOR ----------------
CRISIS_PATTERNS = [
    r"\bsuicid(e|al|er)\b", r"\bkill myself\b", r"\bend my life\b",
    r"\bwant to die\b", r"\bi want to die\b", r"\bself[-\s]?harm\b",
    r"\bhurt myself\b", r"\bcut(ting)?\b", r"\boverdose\b",
    r"\bjump off\b", r"\bno reason to live\b", r"\bcan't go on\b",
    r"\bending it\b", r"انتحار", r"نحب نموت", r"باش نقتل روحي",
    r"باش نأذي روحي", r"نأذي روحي"
]

EMERGENCY_PATTERNS = [
    r"\bcan't breathe\b", r"\bcannot breathe\b", r"\btrouble breathing\b",
    r"\bshortness of breath\b", r"\bbreathing difficulty\b", r"\bchoking\b",
    r"\bchest pain\b", r"\bsevere chest pain\b", r"\bpressure in (my )?chest\b",
    r"\bfaint(ing)?\b", r"\bunconscious\b", r"\bseizure\b", r"\bstroke\b",
    r"\bslurred speech\b", r"\bface droop\b", r"\bcan't move\b", r"\bblue lips\b",
    r"\bpanic attack\b", r"\bi'?m having a panic attack\b", r"\bi'?m panicking\b",
    r"\bheart racing\b", r"\bpalpitations\b", r"\bfeel like (i am|i'm) dying\b",
    r"مانجمش نتنفس", r"ضيق نفس", r"وجع في الصدر", r"وجيعة صدر", r"ألم في الصدر",
    r"طيحت مغشي", r"دوخة قوية", r"صرع"
]

MENTAL_HEALTH_URGENT_PATTERNS = [
    r"\bsevere depression\b", r"\bvery depressed\b", r"\bextremely depressed\b",
    r"\bhopeless\b", r"\bworthless\b", r"\bi can't function\b",
    r"\bcan't get out of bed\b", r"\bcrying all day\b", r"\bnot sleeping\b.*\bdays\b",
    r"\bno sleep\b.*\bdays\b", r"\bhearing voices\b", r"\bseeing things\b",
    r"\bpsychosis\b", r"\bparanoid\b", r"\bmanic\b",
    r"اكتئاب شديد", r"مانيش قادر", r"حاس روحي ميؤوس", r"نسمع أصوات", r"نرى حاجات"
]

def detect_urgency(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if any(re.search(p, t) for p in CRISIS_PATTERNS):
        return "crisis"
    if any(re.search(p, t) for p in EMERGENCY_PATTERNS):
        return "emergency"
    if any(re.search(p, t) for p in MENTAL_HEALTH_URGENT_PATTERNS):
        return "mental_health_urgent"
    return None

def build_alert_banner(level: str) -> str:
    if not level:
        return ""
    label = level.replace("_", " ").upper()
    header = (
        "🚨 **URGENT ALERT**\n"
        "This is an urgent case. You should check with an expert or go to the nearest ER if needed.\n\n"
        f"**CRISIS DETECTED: {label}**\n\n"
    )
    if level == "crisis":
        return header + (
            "• Possible self-harm / suicide risk.\n"
            "• **Call your local emergency number now** or go to the **nearest ER**.\n"
            "• If possible, **stay with someone you trust** and don’t stay alone.\n"
        )
    if level == "emergency":
        return header + (
            "• Possible medical emergency (breathing/chest pain/fainting/severe panic symptoms).\n"
            "• **Go to the nearest ER immediately** or call emergency services.\n"
            "• If possible, ask someone to stay with you.\n"
        )
    return header + (
        "• Severe mental distress.\n"
        "• Contact a **mental health professional urgently** (today / within 24–48 hours).\n"
        "• If you feel unsafe at any moment, **go to the ER** or call emergency services.\n"
    )

# ---------------- GROQ CLIENT ----------------
# Load API key from environment variable
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

@lru_cache(maxsize=1)
def get_groq_client() -> Groq:
    return Groq(api_key=GROQ_API_KEY)

@trace_llm_call("mental_health_agent", "groq_chat_completions")
def groq_chat(messages: List[Dict[str, str]], temperature: float) -> str:
    """
    Send messages to Groq API.
    Strips metadata from messages as Groq API doesn't support it.
    """
    client = get_groq_client()
    
    # Clean messages: remove metadata and keep only role and content
    cleaned_messages = []
    for msg in messages:
        cleaned_msg = {
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        }
        # Only add role and content (Groq doesn't support metadata)
        cleaned_messages.append(cleaned_msg)
    
    resp = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=cleaned_messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content

# ---------------- CHROMA (RAG) ----------------
@lru_cache(maxsize=1)
def get_chroma_collection():
    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(name=COLLECTION_NAME)

@trace_retrieval("mental_health_agent", "chroma_wellbeing_kb")
def retrieve_relevant_techniques(query: str, k: int = 4) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        return []
    if TEST_MODE:
        return []
    col = get_chroma_collection()
    results = col.query(
        query_texts=[query],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    docs: List[Dict[str, Any]] = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0] or [{} for _ in documents]
    for doc, meta in zip(documents, metadatas):
        docs.append({"text": doc, "metadata": meta})
    return docs

def format_rag_context(docs: List[Dict[str, Any]]) -> str:
    if not docs:
        return "No specific internal techniques found."
    chunks: List[str] = []
    for i, d in enumerate(docs, start=1):
        title = (d.get("metadata") or {}).get("title", f"Technique {i}")
        chunks.append(f"[{i}] {title}\n{d.get('text', '')}".strip())
    return "\n\n".join(chunks)


# ---------------- MENTAL HEALTH LOGIC ----------------
@trace_llm_call("mental_health_agent", "analyze_situation")
def analyze_situation(
    user_input: str,
    rag_context: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Structured analysis: emotions, triggers, cognitive patterns, risk.
    """
    history = history or []

    system = {
        "role": "system",
        "content": (
            "You are a mental wellbeing coach. Be supportive, clear, and practical. "
            "Do NOT claim to be a doctor. Ask gentle clarifying questions when needed. "
            "If crisis/emergency risk appears, prioritize safety guidance."
        ),
    }

    prompt = {
        "role": "user",
        "content": (
            "Analyze the user's situation.\n\n"
            f"User message:\n{user_input}\n\n"
            f"Relevant internal techniques/context:\n{rag_context}\n\n"
            "Return a concise structured analysis with:\n"
            "- emotions\n- possible triggers\n- cognitive patterns\n- risk level (low/medium/high)\n- what to focus on next\n"
        ),
    }

    messages = [system] + history[-6:] + [prompt]
    return groq_chat(messages, temperature=ANALYSIS_TEMP)


@trace_llm_call("mental_health_agent", "generate_plan")
def generate_plan(
    user_input: str,
    rag_context: str,
    analysis: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Generates the supportive response.
    NOTE: The alert banner is added in agent.py (or you can add it here too).
    """
    history = history or []

    urgency = detect_urgency(user_input)

    system = {
        "role": "system",
        "content": (
            "You are a mental wellbeing coach. Provide actionable steps, short and clear. "
            "Be empathetic. Include 1-2 questions to continue the conversation.\n\n"
            "Safety rule:\n"
            "- If crisis/emergency signals appear, encourage urgent help (ER/emergency number) first.\n"
            "- Do not provide medical diagnosis.\n"
        ),
    }

    safety_hint = ""
    if urgency == "crisis":
        safety_hint = (
            "User may be at risk of self-harm/suicide. Prioritize immediate safety and encourage emergency services/ER. "
            "Ask if they are safe and if someone is with them.\n\n"
        )
    elif urgency == "emergency":
        safety_hint = (
            "User may have urgent medical symptoms (breathing/chest pain/fainting/severe panic). "
            "Encourage urgent medical evaluation (ER/emergency number).\n\n"
        )
    elif urgency == "mental_health_urgent":
        safety_hint = (
            "User may be in severe mental distress. Encourage rapid professional support (today/24–48h) and safety planning.\n\n"
        )

    prompt = {
        "role": "user",
        "content": (
            f"{safety_hint}"
            "Create a helpful response to the user.\n\n"
            f"User message:\n{user_input}\n\n"
            f"Analysis:\n{analysis}\n\n"
            f"Relevant internal techniques/context:\n{rag_context}\n\n"
            "Response requirements:\n"
            "- Empathetic opening (1–2 lines)\n"
            "- 3 to 6 actionable steps (grounding/breathing OK)\n"
            "- Encourage professional help when needed\n"
            "- End with 1–2 short questions\n"
        ),
    }

    messages = [system] + history[-6:] + [prompt]
    return groq_chat(messages, temperature=PLAN_TEMP)


@trace_llm_call("mental_health_agent", "continue_conversation")
def continue_conversation(
    user_input: str,
    history: List[Dict[str, str]],
    rag_context: str,
) -> str:
    """
    Ongoing chat: supportive response using history + optional RAG context.
    """
    urgency = detect_urgency(user_input)

    system = {
        "role": "system",
        "content": (
            "You are a mental wellbeing assistant. Keep responses supportive, specific, and practical. "
            "Use the conversation history. Avoid medical diagnosis.\n\n"
            "Safety rule: If crisis/emergency signals appear, encourage urgent help first.\n"
        ),
    }

    safety_hint = ""
    if urgency == "crisis":
        safety_hint = "User may be in crisis. Encourage emergency services/ER first, then provide brief support.\n\n"
    elif urgency == "emergency":
        safety_hint = "User may have urgent medical symptoms. Encourage ER/emergency number first.\n\n"
    elif urgency == "mental_health_urgent":
        safety_hint = "User may need urgent mental health support. Encourage professional help soon.\n\n"

    prompt = {
        "role": "user",
        "content": (
            f"{safety_hint}"
            f"User message:\n{user_input}\n\n"
            f"Helpful context (if any):\n{rag_context}\n\n"
            "Reply naturally, with practical help and 1 gentle question."
        ),
    }

    messages = [system] + history[-12:] + [prompt]
    return groq_chat(messages, temperature=CHAT_TEMP)
