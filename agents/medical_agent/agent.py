# agents/medical_agent/agent.py
from __future__ import annotations
import os
import re
import time
import json
from typing import Dict, Any, List, Optional, TypedDict, Tuple
from dataclasses import dataclass
from groq import Groq
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from duckduckgo_search import DDGS
from langdetect import detect as detect_lang
import hashlib

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")

EMB_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # Load from environment variable
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

RETRIEVER_K = 5
MAX_WEB_RESULTS = 4
MAX_HISTORY = 6  # Keep more context for better conversations

# ============================================================
# TYPE DEFINITIONS
# ============================================================
class MedicalAgentState(TypedDict):
    """Enhanced state for medical agent workflow"""
    user_input: str
    agent_output: Optional[str]
    current_agent: str
    next_agent: Optional[str]
    metadata: Dict[str, Any]
    messages: List[Dict[str, str]]
    
    # Medical-specific fields
    medical_context: List[str]
    web_sources: List[Dict[str, str]]
    confidence_score: float
    language: str
    requires_refinement: bool
    evaluation_result: Optional[Dict[str, Any]]
    safety_checks_passed: bool
    # New: Conversation tracking
    should_ask_followup: bool
    followup_question: Optional[str]
    conversation_topic: Optional[str]

@dataclass
class UnderstandingPayload:
    """Payload from understanding agent"""
    intent: str
    language: Optional[str]
    query: str
    keywords: List[str]
    confidence: float

# ============================================================
# GROQ LLM WRAPPER WITH BETTER CONFIGURATION
# ============================================================
class GroqLLMWrapper:
    """Simple wrapper for Groq API with conversational tone"""
    
    def __init__(self, api_key: str, model: str = GROQ_MODEL, temperature: float = 0.7):
        self.client = Groq(api_key=api_key)
        self.model = model
        self.temperature = temperature  # Higher temp for more natural responses
    
    def invoke(self, prompt: str) -> str:
        """Call Groq API with the prompt"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a warm, empathetic medical assistant named Dr. Sahatek who speaks like a real doctor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=600
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Groq API error: {e}")
            return "I'm having trouble accessing medical information right now. For urgent medical concerns, please contact a healthcare provider directly."

# ============================================================
# CONVERSATION MANAGER
# ============================================================
class ConversationManager:
    """Manages conversation flow, follow-up questions, and context"""
    
    def __init__(self, max_history: int = MAX_HISTORY):
        self.conversation_history = []
        self.max_history = max_history
        self.current_topic = None
        self.followup_intent = None
        
    def add_exchange(self, user_message: str, assistant_message: str):
        """Add a conversation exchange to history"""
        self.conversation_history.append({
            "user": user_message,
            "assistant": assistant_message,
            "timestamp": time.time()
        })
        
        # Keep history manageable
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
    
    def get_formatted_history(self, include_last: int = 3) -> str:
        """Get formatted conversation history"""
        if not self.conversation_history:
            return "No conversation history yet."
        
        recent = self.conversation_history[-include_last:] if len(self.conversation_history) > include_last else self.conversation_history
        formatted = []
        for exchange in recent:
            formatted.append(f"Patient: {exchange['user']}")
            formatted.append(f"Doctor: {exchange['assistant']}")
        return "\n".join(formatted)
    
    def analyze_for_followup(self, query: str, response: str) -> Tuple[bool, Optional[str]]:
        """Analyze if we should ask a follow-up question"""
        query_lower = query.lower()
        
        # Topics that often need clarification
        followup_topics = {
            "pain": "Could you tell me more about the pain? Is it sharp, dull, throbbing, or burning?",
            "fever": "How high is the fever, and how long has it been going on?",
            "cough": "Is the cough dry or productive (bringing up mucus)?",
            "rash": "Can you describe the rash? Is it itchy, painful, or spreading?",
            "headache": "Where is the headache located, and how would you describe the pain?",
            "stomach": "Is there any nausea, vomiting, or changes in bowel movements?",
            "fatigue": "How long have you been feeling fatigued, and does it improve with rest?",
            "anxiety": "What situations trigger your anxiety, and how does it affect your daily life?",
            "allergy": "Do you know what triggered the reaction, and have you had similar reactions before?"
        }
        
        # Check if query mentions symptoms that need clarification
        for topic, followup in followup_topics.items():
            if topic in query_lower and "what are" not in query_lower and "what is" not in query_lower:
                # Don't ask follow-up for general information queries
                if not self._is_general_inquiry(query_lower):
                    return True, followup
        
        return False, None
    
    def _is_general_inquiry(self, query: str) -> bool:
        """Check if query is a general information request"""
        general_patterns = [
            "what are", "what is", "symptoms of", "signs of", 
            "how to recognize", "how to identify", "information about",
            "tell me about", "explain", "describe", "define"
        ]
        return any(pattern in query for pattern in general_patterns)

# ============================================================
# MEDICAL KNOWLEDGE BASE
# ============================================================
class MedicalKnowledgeBase:
    """Medical knowledge base using ChromaDB"""
    
    def __init__(self, path: str):
        print(f"🔌 Initializing Medical Knowledge Base from: {path}")
        try:
            if not os.path.exists(path):
                print(f"❌ Vector store directory does not exist: {path}")
                self.client = None
                self.collection = None
                self.embedding_model = None
                return
            
            self.embedding_model = SentenceTransformer(EMB_MODEL)
            print(f"✅ Embedding model loaded: {EMB_MODEL}")
            
            self.client = chromadb.PersistentClient(
                path=path,
                settings=Settings(anonymized_telemetry=False)
            )
            
            try:
                self.collection = self.client.get_or_create_collection(
                    name="medical_knowledge_base",
                    metadata={"description": "Medical emergency and first aid knowledge base"}
                )
                print(f"✅ ChromaDB collection loaded: {self.collection.count()} documents")
            except Exception as e:
                print(f"❌ Failed to get collection: {e}")
                self.collection = None
            
            self.query_cache = {}
            
        except Exception as e:
            print(f"❌ Failed to load Medical Knowledge Base: {e}")
            self.client = None
            self.collection = None
            self.embedding_model = None
            self.query_cache = {}
    
    def retrieve_context(self, query: str, k: int = RETRIEVER_K) -> List[str]:
        """Retrieve relevant medical context"""
        if not self.collection:
            print("⚠️ ChromaDB collection not loaded")
            return []
        
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self.query_cache:
            return self.query_cache[cache_key]
        
        try:
            query_embedding = self.embedding_model.encode(
                query, 
                normalize_embeddings=True
            ).tolist()
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                include=["documents", "metadatas", "distances"]
            )
            
            relevant_docs = []
            if results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    score = 1 - results["distances"][0][i] if results["distances"] else 0.5
                    if score > 0.3:
                        relevant_docs.append(doc)
            
            print(f"📄 Retrieved {len(relevant_docs)} relevant documents")
            self.query_cache[cache_key] = relevant_docs
            return relevant_docs
            
        except Exception as e:
            print(f"⚠️ Knowledge base retrieval error: {e}")
            return []

# ============================================================
# MEDICAL RESPONSE GENERATOR
# ============================================================
class MedicalResponseGenerator:
    """Generates warm, doctor-like medical responses"""
    
    def __init__(self, llm: GroqLLMWrapper):
        self.llm = llm
    
    def generate_response(self, query: str, context: List[str], 
                         conversation_history: str, language: str,
                         should_ask_followup: bool = False) -> str:
        """Generate a warm, empathetic medical response"""
        
        # Doctor personas for different languages
        doctor_personas = {
            "en": """You are Dr. Sahatek, a warm, empathetic medical doctor. You speak like a real doctor talking to a patient in your office.

Your communication style:
- Warm and friendly: "I understand your concern about..."
- Empathetic: "That must be worrying for you..."
- Clear and simple: Break down medical terms
- Conversational: Use "you" and "we" instead of formal language
- Reassuring: Offer hope and practical advice
- Natural: No robotic lists or formal section headers
- Safety-conscious: Gently emphasize when to seek urgent care

Never use: **bold headers**, formal lists like "1.", robotic phrasing, or legal disclaimers.
Do use: Natural paragraphs, bullet points only when helpful, and a caring tone.""",
            
            "fr": """Tu es le Dr. Sahatek, un médecin chaleureux et empathique. Tu parles comme un vrai médecin parlant à un patient.

Ton style de communication:
- Chaleureux et amical: "Je comprends votre inquiétude concernant..."
- Empathique: "Cela doit être inquiétant pour vous..."
- Clair et simple: Explique les termes médicaux
- Conversationnel: Utilise "vous" et "nous" au lieu d'un langage formel
- Rassurant: Offre de l'espoir et des conseils pratiques
- Naturel: Pas de listes robotiques ou d'en-têtes formels
- Conscient de la sécurité: Souligne doucement quand consulter d'urgence

N'utilise jamais: **en-têtes en gras**, listes formelles comme "1.", phrases robotiques, ou avertissements juridiques.
Utilise: Paragraphes naturels, puces seulement si utiles, et un ton attentionné.""",
            
            "ar": """أنت د. صحتك، طبيب دافئ ومتعاطف. تتحدث كطبيب حقيقي يتحدث مع مريض في عيادته.

أسلوبك في التواصل:
- دافئ وودود: "أتفهم قلقك بشأن..."
- متعاطف: "يجب أن يكون ذلك مقلقًا لك..."
- واضح وبسيط: فسر المصطلحات الطبية
- محادثة: استخدم "أنت" و"نحن" بدلاً من اللغة الرسمية
- مطمئن: قدم الأمل والنصائح العملية
- طبيعي: لا تستخدم قوائم روبوتية أو عناوين رسمية
- واعي بالسلامة: أكد بلطف متى تطلب الرعاية العاجلة

لا تستخدم أبدًا: **عناوين عريضة**، قوائم رسمية مثل "١."، عبارات روبوتية، أو إخلاء مسؤولية قانونية.
استخدم: فقرات طبيعية، نقاط تعداد فقط إذا كانت مفيدة، ونبرة رعاية."""
        }
        
        persona = doctor_personas.get(language, doctor_personas["en"])
        
        # Format context
        if context:
            context_text = "\n".join([f"Medical information: {c[:250]}..." for c in context[:2]])
        else:
            context_text = "No specific medical information found in database."
        
        # Build prompt
        prompt = f"""{persona}

Previous conversation:
{conversation_history}

Medical information available:
{context_text}

Patient's question: {query}

Your task: Provide a warm, doctor-like response. Be empathetic, clear, and helpful.

Important guidelines:
1. Speak naturally like a doctor to a patient
2. If it's an emergency (heart attack, stroke, etc.), gently but firmly recommend immediate medical care
3. For symptoms, ask clarifying questions if needed
4. Always end with an offer to help further: "Is there anything else you'd like to know?" or "How else can I help you today?"

Your response (as Dr. Sahatek):"""

        try:
            response = self.llm.invoke(prompt)
            
            # Add follow-up question if needed
            if should_ask_followup:
                followup_prompt = f"""Based on this conversation:
{conversation_history}

And your last response: {response[:100]}...

The patient mentioned symptoms that need clarification. Ask ONE gentle, clarifying question to better understand their situation.

Your follow-up question (be warm and natural):"""
                
                followup = self.llm.invoke(followup_prompt)
                response = response.rstrip(".") + f"\n\n{followup}"
            
            # Always end with an offer to help
            if not response.strip().endswith("?"):
                closing_phrases = {
                    "en": "\n\nIs there anything else you'd like me to clarify about this?",
                    "fr": "\n\nY a-t-il autre chose que vous aimeriez que je clarifie à ce sujet?",
                    "ar": "\n\nهل هناك أي شيء آخر تود أن أوضحه لك بشأن هذا؟"
                }
                response += closing_phrases.get(language, closing_phrases["en"])
            
            return response
            
        except Exception as e:
            print(f"⚠️ Response generation error: {e}")
            return "I understand you're looking for medical information. For the most accurate advice, please consult with a healthcare provider who can evaluate your specific situation."

# ============================================================
# MAIN LANGGRAPH AGENT - REDESIGNED
# ============================================================
class MedicalLangGraphAgent:
    """Medical agent with conversational tone and follow-up capability"""
    
    def __init__(self):
        print("👨‍⚕️ Initializing Dr. Sahatek Medical Assistant...")
        
        # Core components
        self.knowledge_base = MedicalKnowledgeBase(CHROMA_DB_PATH)
        self.conversation_manager = ConversationManager()
        
        # Use Groq LLM
        if GROQ_API_KEY:
            self.llm = GroqLLMWrapper(api_key=GROQ_API_KEY, model=GROQ_MODEL, temperature=0.7)
            self.response_generator = MedicalResponseGenerator(self.llm)
            print(f"✅ Medical AI initialized with conversational tone")
        else:
            print("⚠️ GROQ_API_KEY not set. Using fallback responses.")
            self.llm = None
            self.response_generator = None
    
    def _determine_language(self, query: str, payload_language: Optional[str]) -> str:
        """Detect language with fallbacks"""
        if payload_language and payload_language in ["en", "fr", "ar", "aeb"]:
            return payload_language
        
        try:
            detected = detect_lang(query)
            if detected.startswith("fr"):
                return "fr"
            elif detected.startswith("ar"):
                if any(word in query.lower() for word in ["باش", "ف", "ش", "علاه"]):
                    return "aeb"
                return "ar"
            return "en"
        except:
            return "en"
    
    def process_query(self, state: MedicalAgentState) -> MedicalAgentState:
        """Main processing method - warm, conversational responses"""
        print(f"👨‍⚕️ Dr. Sahatek processing: '{state.get('user_input')}'")
        
        # Extract inputs
        user_input = state.get("user_input", "")
        payload_data = state.get("metadata", {}).get("understanding_agent", {})
        
        # Create payload
        payload = UnderstandingPayload(
            intent=payload_data.get("intent", "medical_qa"),
            language=payload_data.get("language"),
            query=user_input,
            keywords=payload_data.get("keywords", []),
            confidence=payload_data.get("confidence", 0.5)
        )
        
        # Determine language
        language = self._determine_language(user_input, payload.language)
        print(f"🌐 Language: {language}")
        
        # Step 1: Retrieve medical knowledge
        print("📚 Consulting medical knowledge...")
        kb_context = self.knowledge_base.retrieve_context(user_input)
        
        # Step 2: Get conversation history
        conversation_history = self.conversation_manager.get_formatted_history()
        
        # Step 3: Analyze for follow-up questions
        should_ask_followup = False
        followup_question = None
        
        if len(self.conversation_manager.conversation_history) > 0:
            should_ask_followup, followup_question = self.conversation_manager.analyze_for_followup(
                user_input, self.conversation_manager.conversation_history[-1]["assistant"]
            )
        
        # Step 4: Generate response
        print("💬 Preparing doctor's response...")
        
        if not self.response_generator:
            # Fallback response
            answer = "Hello, I'm Dr. Sahatek. I understand you're looking for medical information. For personalized medical advice, please consult with a healthcare provider."
        else:
            answer = self.response_generator.generate_response(
                query=user_input,
                context=kb_context,
                conversation_history=conversation_history,
                language=language,
                should_ask_followup=should_ask_followup
            )
        
        # Step 5: Update conversation
        self.conversation_manager.add_exchange(user_input, answer)
        
        # Step 6: Determine if escalation is needed (only for clear emergencies)
        next_agent = self._determine_next_agent(user_input, answer)
        
        # Step 7: Update state
        state.update({
            "agent_output": answer,
            "current_agent": "medical_qa",
            "next_agent": next_agent,
            "medical_context": kb_context,
            "web_sources": [],
            "confidence_score": 0.9,
            "language": language,
            "requires_refinement": False,
            "evaluation_result": None,
            "safety_checks_passed": True,
            "should_ask_followup": should_ask_followup,
            "followup_question": followup_question,
            "conversation_topic": self._extract_topic(user_input)
        })
        
        print(f"✅ Response ready ({len(answer)} characters)")
        return state
    
    def _extract_topic(self, query: str) -> str:
        """Extract main topic from query"""
        medical_topics = [
            "heart", "asthma", "diabetes", "blood pressure", "fever",
            "pain", "headache", "stomach", "cough", "rash", "allergy",
            "anxiety", "depression", "injury", "burn", "fracture"
        ]
        
        query_lower = query.lower()
        for topic in medical_topics:
            if topic in query_lower:
                return topic
        return "general"
    
    def _determine_next_agent(self, query: str, answer: str) -> Optional[str]:
        """Determine if escalation is needed - only for clear personal emergencies"""
        query_lower = query.lower()
        
        # Clear personal emergency indicators
        personal_emergency_patterns = [
            r"i (?:am|'m) having (?:a )?heart attack",
            r"i (?:am|'m) having (?:a )?stroke",
            r"i (?:can't|cannot) breathe",
            r"i (?:am|'m) (?:bleeding|hemorrhaging) heavily",
            r"i (?:am|'m) unconscious",
            r"i (?:want|need) to kill myself",
            r"i (?:am|'m) suicidal"
        ]
        
        for pattern in personal_emergency_patterns:
            if re.search(pattern, query_lower):
                print(f"🚨 Clear personal emergency detected - escalating to triage")
                return "triage"
        
        return None

# ============================================================
# LANGGRAPH NODE FUNCTION
# ============================================================
_medical_agent_instance = None

def medical_qa_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node function - warm, conversational medical assistant
    """
    print(f"👨‍⚕️ Dr. Sahatek Medical Assistant called")
    print(f"📝 Patient's question: {state.get('user_input', '')[:80]}...")
    
    global _medical_agent_instance
    
    if _medical_agent_instance is None:
        _medical_agent_instance = MedicalLangGraphAgent()
    
    # Convert state to typed dict format
    typed_state = MedicalAgentState(
        user_input=state.get("user_input", ""),
        agent_output=state.get("agent_output"),
        current_agent=state.get("current_agent", "medical_qa"),
        next_agent=state.get("next_agent"),
        metadata=state.get("metadata", {}),
        messages=state.get("messages", []),
        medical_context=state.get("medical_context", []),
        web_sources=state.get("web_sources", []),
        confidence_score=state.get("confidence_score", 0.0),
        language=state.get("language", "en"),
        requires_refinement=state.get("requires_refinement", False),
        evaluation_result=state.get("evaluation_result"),
        safety_checks_passed=state.get("safety_checks_passed", False),
        should_ask_followup=state.get("should_ask_followup", False),
        followup_question=state.get("followup_question"),
        conversation_topic=state.get("conversation_topic")
    )
    
    # Process through agent
    result_state = _medical_agent_instance.process_query(typed_state)
    
    print(f"✅ Dr. Sahatek consultation complete")
    print(f"⏭️ Next agent: {result_state.get('next_agent') or 'Continue conversation'}")
    
    # Convert back to regular dict
    result_dict = dict(result_state)
    
    # Clear routing flags
    if "forced_agent" in result_dict:
        result_dict["forced_agent"] = None
    if "preferred_agent" in result_dict:
        result_dict["preferred_agent"] = None
    
    return result_dict

# ============================================================
# DEMO/TEST SCRIPT
# ============================================================
if __name__ == "__main__":
    print("🧪 Testing Dr. Sahatek Medical Assistant...")
    print("=" * 60)
    
    # Test a conversation flow
    test_conversation = [
        "I've been having chest pain for the last hour",
        "It feels like pressure and sometimes goes to my left arm",
        "What should I do?",
        "Can you tell me about asthma attacks?",
        "What are the symptoms?"
    ]
    
    agent = MedicalLangGraphAgent()
    
    for i, query in enumerate(test_conversation):
        print(f"\n{'='*50}")
        print(f"💬 Turn {i+1}: Patient says: '{query}'")
        print('='*50)
        
        test_state = MedicalAgentState(
            user_input=query,
            agent_output=None,
            current_agent="medical_qa",
            next_agent=None,
            metadata={
                "understanding_agent": {
                    "intent": "medical_qa",
                    "language": "en",
                    "query": query,
                    "keywords": query.lower().split(),
                    "confidence": 0.9
                }
            },
            messages=[],
            medical_context=[],
            web_sources=[],
            confidence_score=0.0,
            language="en",
            requires_refinement=False,
            evaluation_result=None,
            safety_checks_passed=False,
            should_ask_followup=False,
            followup_question=None,
            conversation_topic=None
        )
        
        result = agent.process_query(test_state)
        
        print(f"\n👨‍⚕️ Dr. Sahatek's response:")
        print("-" * 40)
        print(result['agent_output'])
        print("-" * 40)
        
        if result['should_ask_followup']:
            print(f"🔍 Follow-up intent detected")
        
        time.sleep(0.5)
    
    print("\n" + "="*60)
    print("✅ Dr. Sahatek Medical Assistant test complete!")
    print("The assistant now sounds like a real doctor with conversational flow!")