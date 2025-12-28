# agents/understanding_agent/agent.py
import os
import json
import re
import hashlib
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Core dependencies only
from langdetect import detect, LangDetectException
from groq import Groq

# Speech processing (optional)
try:
    from vosk import Model, KaldiRecognizer
    import sounddevice as sd
    import queue
    from agents.speech.transcription import TranscriptionService
    SPEECH_ENABLED = True
except ImportError:
    SPEECH_ENABLED = False
    TranscriptionService = None

# ============================================================
# SIMPLE CONFIGURATION
# ============================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # Load from environment variable
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ============================================================
# SIMPLE DATA STRUCTURES
# ============================================================
class Intent(Enum):
    MEDICAL_QA = "medical_qa"
    TRIAGE = "triage"
    MENTAL_HEALTH = "mental_health"
    RUMOR = "rumor"
    GREETING = "greeting"
    CLARIFICATION_NEEDED = "clarification_needed"
    OUT_OF_SCOPE = "out_of_scope"

@dataclass
class UserMessage:
    text: str
    language: str  # en, fr, ar, aeb
    is_audio: bool = False
    audio_data: Optional[bytes] = None

@dataclass
class AgentDecision:
    intent: Intent
    route_to: Optional[str]  # None means handle here
    response: str
    confidence: float
    needs_clarification: bool = False
    facility_type: Optional[str] = None  # For direct facility requests

# ============================================================
# ULTRA-SIMPLIFIED SPEECH HANDLER
# ============================================================
class SpeechHandler:
    """Only handles speech-to-text, nothing else"""
    
    def __init__(self):
        self.transcription_service = None
        self.model_paths = [
            "E:/9raya_4eme_Sem1/Projet_Ia/Modele_Text_to_Speech_Derja/Modele_huhugging/vosk-model/vosk-model",
            os.path.join(os.path.dirname(__file__), "..", "..", "maaaheeeerrr", "Modele_huhugging", "vosk-model", "vosk-model"),
        ]
    
    def _get_model_path(self):
        """Find available model path"""
        for path in self.model_paths:
            if os.path.exists(path):
                return path
        return None
    
    def _get_transcription_service(self):
        """Get or create transcription service instance"""
        if self.transcription_service is None and TranscriptionService:
            model_path = self._get_model_path()
            try:
                self.transcription_service = TranscriptionService.get_instance(model_path)
            except Exception as e:
                print(f"⚠️ Could not initialize transcription service: {e}")
                return None
        return self.transcription_service
    
    def transcribe(self, audio_data: bytes) -> str:
        """Simple transcription using the new transcription service"""
        if not SPEECH_ENABLED or not TranscriptionService:
            return ""
        
        service = self._get_transcription_service()
        if not service:
            # Fallback to old method if service unavailable
            return self._transcribe_fallback(audio_data)
        
        try:
            # Use the new transcription service
            result = service.transcribe_audio_data(audio_data)
            return result.strip()
        except Exception as e:
            print(f"⚠️ Transcription error: {e}")
            # Fallback to old method
            return self._transcribe_fallback(audio_data)
    
    def _transcribe_fallback(self, audio_data: bytes) -> str:
        """Fallback transcription method (old implementation)"""
        try:
            from vosk import Model, KaldiRecognizer
            model_path = self._get_model_path()
            if not model_path:
                return ""
            
            model = Model(model_path)
            recognizer = KaldiRecognizer(model, 16000)
            if recognizer.AcceptWaveform(audio_data):
                result = json.loads(recognizer.Result())
                return result.get("text", "").strip()
            return ""
        except Exception as e:
            print(f"⚠️ Fallback transcription error: {e}")
            return ""

# ============================================================
# CORE UNDERSTANDING AGENT - SIMPLE & RELIABLE
# ============================================================
class UnderstandingAgent:
    """
    Simple understanding agent that:
    1. Listens to user
    2. Understands intent
    3. Routes to correct agent
    That's it.
    """
    
    def __init__(self):
        print("🤖 Initializing Simple Understanding Agent...")
        self.groq = Groq(api_key=GROQ_API_KEY)
        self.speech = SpeechHandler() if SPEECH_ENABLED else None
        
        # Cache for performance
        self.cache = {}
        
        # Simple language mappings
        self.language_responses = {
            "en": {
                "greeting": "Hello! I'm Sahatek, your medical assistant. I can help with:\n• Medical questions (medical_qa)\n• Symptom assessment (triage)\n• Mental health support (mental_health)\n• Medical rumor verification (rumor)\n\nHow can I help you today?",
                "clarify": "I want to make sure I understand correctly. Could you please provide more details about your medical concern?",
                "out_of_scope": "I specialize in medical assistance only. Please describe your medical concern and I'll help you.",
                "routing": "I understand. Let me connect you to the right specialist..."
            },
            "aeb": {
                "greeting": "السلام! أنا ساهاتيك، المساعد الطبي تاعك. نقدر نعاونك في:\n• أسئلة طبية (medical_qa)\n• تقييم الأعراض (triage)\n• دعم الصحة النفسية (mental_health)\n• تحقق من الشائعات الطبية (rumor)\n\nكيفاش نقدر نعاونك اليوم؟",
                "clarify": "نبغي نتأكد باش نفهم صح. تقدر تعطيني تفاصيل أكثر على القلق الطبي تاعك؟",
                "out_of_scope": "نتخصص في المساعدة الطبية فقط. نرجيوصف القلق الطبي تاعك ونعاونك.",
                "routing": "فهمتك. نرجع نوصلك مع الأخصائي المناسب..."
            },
            "ar": {
                "greeting": "مرحباً! أنا ساهاتيك، مساعدك الطبي. يمكنني المساعدة في:\n• الأسئلة الطبية (medical_qa)\n• تقييم الأعراض (triage)\n• دعم الصحة النفسية (mental_health)\n• التحقق من الشائعات الطبية (rumor)\n\nكيف يمكنني مساعدتك اليوم؟",
                "clarify": "أريد التأكد من فهمي الصحيح. هل يمكنك تقديم المزيد من التفاصيل عن مخاوفك الطبية؟",
                "out_of_scope": "أتخصص في المساعدة الطبية فقط. يرجى وصف مخاوفك الطبية وسأساعدك.",
                "routing": "فهمتك. دعني أوصلك بالمتخصص المناسب..."
            }
        }
    
    # ==================== SIMPLE LANGUAGE DETECTION ====================
    
    def detect_language(self, text: str) -> str:
        """Detect language with fallbacks"""
        if not text.strip():
            return "en"
        
        try:
            # Try langdetect first
            lang = detect(text)
            
            # Check for Tunisian Arabic
            if any(word in text.lower() for word in ["باش", "ف", "ش", "علاه", "برشا"]):
                return "aeb"
            
            # Check for Arabic script
            if re.search(r'[\u0600-\u06FF]', text):
                return "ar"
            
            # Map to supported languages
            if lang.startswith("en"):
                return "en"
            elif lang.startswith("fr"):
                return "fr"
            elif lang.startswith("ar"):
                return "ar"
            return "en"
            
        except:
            # Simple fallback
            if re.search(r'[\u0600-\u06FF]', text):
                return "ar"
            return "en"
    
    # ==================== SIMPLE INTENT CLASSIFICATION ====================
    
    def classify_intent(self, text: str, language: str) -> AgentDecision:
        """
        Simple intent classification using LLM
        Returns: what to do next
        """
        # Quick check for short answers that should go to triage
        text_lower = text.lower().strip()
        short_answers = ["yes", "y", "no", "n", "maybe", "sometimes", "occasionally", "oui", "non", "نعم", "لا", "أي", "لا"]
        
        if text_lower in short_answers:
            print(f"🔍 Detected short answer: '{text}' - routing to triage")
            return AgentDecision(
                intent=Intent.TRIAGE,
                route_to="triage",
                response=self.language_responses.get(language, self.language_responses["en"])["routing"],
                confidence=0.9,
                needs_clarification=False
            )
        
        # Check for direct facility requests (e.g., "show me nearest pharmacies", "where is the nearest hospital")
        facility_keywords = {
            "pharmacy": ["pharmacy", "pharmacies", "pharmacie", "صيدلية", "صيدليات", "pharma"],
            "hospital": ["hospital", "hospitals", "مستشفى", "مستشفيات", "hopital"],
            "clinic": ["clinic", "clinics", "عيادة", "عيادات", "clinique"],
            "doctor": ["doctor", "doctors", "طبيب", "أطباء", "medecin", "medecins"],
            "urgent_care": ["urgent care", "urgence", "طوارئ", "emergency room", "er"]
        }
        
        facility_request_patterns = [
            "show me", "where is", "find", "nearest", "closest", "nearby",
            "أين", "أعطني", "أوجد", "أقرب", "أقرب", "قريب"
        ]
        
        # Check if user is asking for a facility
        is_facility_request = any(pattern in text_lower for pattern in facility_request_patterns)
        
        if is_facility_request:
            # Extract facility type
            detected_facility = None
            for facility_type, keywords in facility_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    detected_facility = facility_type.upper()
                    if facility_type == "pharmacy":
                        detected_facility = "PHARMACY"
                    elif facility_type == "hospital":
                        detected_facility = "HOSPITAL"
                    elif facility_type == "clinic":
                        detected_facility = "CLINIC"
                    elif facility_type == "doctor":
                        detected_facility = "DOCTOR"
                    elif facility_type == "urgent_care":
                        detected_facility = "URGENT_CARE"
                    break
            
            if detected_facility:
                print(f"🔍 Detected facility request: '{text}' - routing to orientation with {detected_facility}")
                return AgentDecision(
                    intent=Intent.TRIAGE,  # Use TRIAGE intent but route to orientation
                    route_to="orientation",  # Route directly to orientation
                    response=self.language_responses.get(language, self.language_responses["en"])["routing"],
                    confidence=0.95,
                    needs_clarification=False,
                    facility_type=detected_facility  # Pass facility type in decision
                )
        
        # Check cache first
        cache_key = hashlib.md5(f"{text}_{language}".encode()).hexdigest()[:10]
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        print(f"🔍 Analyzing: '{text[:50]}...'")
        
        # Prepare prompt based on language
        prompt = self._create_intent_prompt(text, language)
        
        try:
            # Call Groq API
            response = self.groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are an intent classifier for a medical assistant. Return JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            result = self._parse_json_response(result_text)
            
            # Create decision
            decision = self._create_decision_from_result(result, language, text)
            
            # Cache it
            self.cache[cache_key] = decision
            
            # Keep cache size reasonable
            if len(self.cache) > 100:
                self.cache.pop(next(iter(self.cache)))
            
            return decision
            
        except Exception as e:
            print(f"⚠️ LLM error, using fallback: {e}")
            return self._fallback_classification(text, language)
    
    def _create_intent_prompt(self, text: str, language: str) -> str:
        """Create simple prompt for intent classification"""
        
        prompts = {
            "en": f"""Classify this user message for a medical assistant:

Message: "{text}"

Possible intents:
1. medical_qa - General medical questions (what is X, symptoms of Y)
2. triage - Emergency symptoms, "should I go to hospital", urgent care
3. mental_health - Depression, anxiety, stress, emotional issues
4. rumor - "Is it true that...", medical rumors
5. greeting - Hello, hi, greetings
6. clarification_needed - Vague, unclear, needs more details
7. out_of_scope - Not medical, nonsense, unrelated

Return JSON with:
- intent: one of the above
- confidence: 0.0 to 1.0
- needs_clarification: true/false (if confidence < 0.7)

Example: {{"intent": "medical_qa", "confidence": 0.9, "needs_clarification": false}}""",
            
            "aeb": f"""صنّف هادي الرسالة لمساعد طبي:

الرسالة: "{text}"

النوايا الممكنة:
1. medical_qa - أسئلة طبية عامة (شنوة X، أعراض Y)
2. triage - أعراض طارئة، "نروح للمستشفى ولا لا"، رعاية عاجلة
3. mental_health - اكتئاب، قلق، توتر، مشاكل عاطفية
4. rumor - "هاديك حقيقة ولا لا..."، شائعات طبية
5. greeting - سلام، أهلا، تحية
6. clarification_needed - مبهم، غير واضح، يحتاج تفاصيل أكثر
7. out_of_scope - غير طبي، كلام فاضي، غير مرتبط

ارجع JSON مع:
- intent: واحد من فوق
- confidence: من 0.0 ل 1.0
- needs_clarification: true/false (إذا الثقة أقل من 0.7)

مثال: {{"intent": "medical_qa", "confidence": 0.9, "needs_clarification": false}}"""
        }
        
        return prompts.get(language, prompts["en"])
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response"""
        try:
            # Find JSON in response
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
        except:
            pass
        
        # Fallback to empty dict
        return {"intent": "out_of_scope", "confidence": 0.5, "needs_clarification": True}
    
    def _create_decision_from_result(self, result: Dict, language: str, original_text: str) -> AgentDecision:
        """Create decision object from LLM result"""
        
        intent_map = {
            "medical_qa": Intent.MEDICAL_QA,
            "triage": Intent.TRIAGE,
            "mental_health": Intent.MENTAL_HEALTH,
            "rumor": Intent.RUMOR,
            "greeting": Intent.GREETING,
            "clarification_needed": Intent.CLARIFICATION_NEEDED,
            "out_of_scope": Intent.OUT_OF_SCOPE
        }
        
        intent_str = result.get("intent", "out_of_scope")
        intent = intent_map.get(intent_str, Intent.OUT_OF_SCOPE)
        confidence = float(result.get("confidence", 0.5))
        needs_clarification = bool(result.get("needs_clarification", False)) or confidence < 0.7
        
        # Determine routing
        route_map = {
            Intent.MEDICAL_QA: "medical_qa",
            Intent.TRIAGE: "triage",
            Intent.MENTAL_HEALTH: "mental_health",
            Intent.RUMOR: "rumor"
        }
        
        route_to = route_map.get(intent)
        
        # Generate appropriate response
        response = self._generate_response(intent, language, needs_clarification, original_text)
        
        return AgentDecision(
            intent=intent,
            route_to=route_to,
            response=response,
            confidence=confidence,
            needs_clarification=needs_clarification
        )
    
    def _generate_response(self, intent: Intent, language: str, 
                          needs_clarification: bool, original_text: str) -> str:
        """Generate appropriate response based on intent"""
        
        responses = self.language_responses.get(language, self.language_responses["en"])
        
        if needs_clarification:
            return responses["clarify"]
        
        if intent == Intent.GREETING:
            return responses["greeting"]
        
        if intent == Intent.OUT_OF_SCOPE:
            return responses["out_of_scope"]
        
        # For medical intents that will be routed, return empty or minimal message
        # The actual response will come from the specialized agent
        return ""  # Let the next agent handle the response
    
    def _fallback_classification(self, text: str, language: str) -> AgentDecision:
        """Simple keyword-based fallback when LLM fails"""
        
        text_lower = text.lower()
        
        # Check for greetings
        greetings = ["hello", "hi", "hey", "سلام", "أهلا", "السلام"]
        if any(greet in text_lower for greet in greetings):
            return AgentDecision(
                intent=Intent.GREETING,
                route_to=None,
                response=self.language_responses.get(language, self.language_responses["en"])["greeting"],
                confidence=0.8
            )
        
        # Check for medical keywords
        medical_keywords = ["pain", "hurt", "symptom", "fever", "cough", "وجع", "عرض", "حمى"]
        if any(keyword in text_lower for keyword in medical_keywords):
            # Check if it's emergency
            emergency_words = ["emergency", "urgent", "hospital", "طوارئ", "عاجل", "مستشفى"]
            if any(word in text_lower for word in emergency_words):
                return AgentDecision(
                    intent=Intent.TRIAGE,
                    route_to="triage",
                    response=self.language_responses.get(language, self.language_responses["en"])["routing"],
                    confidence=0.7
                )
            else:
                return AgentDecision(
                    intent=Intent.MEDICAL_QA,
                    route_to="medical_qa",
                    response=self.language_responses.get(language, self.language_responses["en"])["routing"],
                    confidence=0.7
                )
        
        # Default to out of scope
        return AgentDecision(
            intent=Intent.OUT_OF_SCOPE,
            route_to=None,
            response=self.language_responses.get(language, self.language_responses["en"])["out_of_scope"],
            confidence=0.6,
            needs_clarification=True
        )
    
    # ==================== MAIN PROCESSING ====================
    
    def process(self, user_input: str, is_audio: bool = False, 
               audio_data: bytes = None) -> Tuple[AgentDecision, UserMessage]:
        """
        Main entry point - process user input
        Returns: (decision, user_message)
        """
        
        # Step 1: Handle audio if present
        if is_audio and audio_data and self.speech:
            print("🎤 Processing audio...")
            user_input = self.speech.transcribe(audio_data)
            if not user_input:
                user_input = "[Could not transcribe audio]"
        
        # Step 2: Detect language
        language = self.detect_language(user_input)
        
        # Create user message object
        user_message = UserMessage(
            text=user_input,
            language=language,
            is_audio=is_audio,
            audio_data=audio_data
        )
        
        # Step 3: Classify intent
        decision = self.classify_intent(user_input, language)
        
        # Step 4: Log result
        print(f"🌍 Language: {language}")
        print(f"🎯 Intent: {decision.intent.value} (Confidence: {decision.confidence:.2f})")
        print(f"🔄 Route to: {decision.route_to or 'HANDLE HERE'}")
        print(f"💬 Response: {decision.response[:50]}...")
        
        return decision, user_message
    
    # ==================== LANGGRAPH INTEGRATION ====================
    
    def router_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph router function
        Simple and reliable
        """
        # Get user input from state
        user_input = state.get("user_input", "").strip()
        metadata = state.get("metadata", {})
        
        # CRITICAL: Check for pending questions or active triage session
        # If there are pending questions, route directly to triage without classification
        pending_questions = state.get("pending_questions", [])
        session_id = state.get("session_id")
        
        # IMPORTANT: Check if this is a NEW request vs answer to pending question
        # If user says something like "i feel depressed", "i have chest pain", etc, 
        # it's a NEW request even if there are pending_questions from triage
        is_likely_new_request = False
        if pending_questions or session_id:
            # Quick check: does this look like a new medical intent?
            new_request_keywords = {
                "depressed": "mental_health",
                "anxious": "mental_health",
                "stressed": "mental_health",
                "sad": "mental_health",
                "suicidal": "mental_health",
                "suicide": "mental_health",
                "mental": "mental_health",
                "emotional": "mental_health",
                "psychiatric": "mental_health",
                "psychology": "mental_health",
                "therapist": "mental_health",
                "therapy": "mental_health",
                "what is": "medical_qa",
                "explain": "medical_qa",
                "symptoms of": "medical_qa",
                "cause of": "medical_qa",
                "how to": "medical_qa",
                "is that true": "rumor",
                "is this": "rumor",
                "is it true": "rumor",
                "is it": "rumor",
                "rumor": "rumor",
                "myth": "rumor",
                "heard in": "rumor",
                "tiktok": "rumor",
                "facebook": "rumor",
                "twitter": "rumor",
                "true or false": "rumor"
            }
            
            user_input_lower = user_input.lower().strip()
            for keyword, detected_intent in new_request_keywords.items():
                if keyword in user_input_lower:
                    print(f"🔀 Detected new request keyword '{keyword}' - classifying as new intent")
                    is_likely_new_request = True
                    break
        
        # If it's a new request, classify it (don't assume it's answering the question)
        if is_likely_new_request:
            print(f"🔀 New request detected despite pending questions - reclassifying intent")
            # Fall through to normal classification below - NEW INTENT overrides pending questions
        elif pending_questions or session_id:
            # Only route to triage if NO new request detected
            print(f"🔄 Active triage session detected (session_id: {session_id}, pending_questions: {len(pending_questions)})")
            print(f"   Routing directly to triage to process answer: '{user_input[:50]}...'")
            return {
                "agent_output": "Processing your answer...",
                "current_agent": "router",
                "next_agent": "triage",  # Route directly to triage
                "should_end": False,
                "intent": "triage",
                "language": metadata.get("language", "en"),
                "metadata": {
                    **metadata,
                    "understanding_agent": {
                        "original_input": user_input,
                        "detected_language": metadata.get("language", "en"),
                        "intent": "triage",
                        "confidence": 1.0,
                        "needs_clarification": False,
                        "routed_due_to_pending_questions": True
                    }
                }
            }
        
        # If no input, send greeting
        if not user_input:
            lang = metadata.get("language", "en")
            greeting = self.language_responses.get(lang, self.language_responses["en"])["greeting"]
            
            return {
                "agent_output": greeting,
                "current_agent": "router",
                "next_agent": None,
                "should_end": False,
                "metadata": metadata
            }
        
        try:
            # Process the input
            decision, user_message = self.process(user_input)
            
            # Prepare result - preserve existing state fields
            result = {
                "agent_output": decision.response,
                "current_agent": "router",
                "next_agent": decision.route_to,
                "should_end": decision.route_to is None,
                "intent": decision.intent.value,
                "language": user_message.language,
                "metadata": {
                    **metadata,
                    "understanding_agent": {
                        "original_input": user_message.text,
                        "detected_language": user_message.language,
                        "intent": decision.intent.value,
                        "confidence": decision.confidence,
                        "needs_clarification": decision.needs_clarification,
                        "router_response": decision.response,  # Keep router response for tracing
                        "routing_to": decision.route_to  # Explicit routing target for LangSmith
                    }
                }
            }
            
            # Preserve location from state (important for direct facility requests)
            if "user_location" in state:
                result["user_location"] = state["user_location"]
                print(f"📍 Preserving user_location in router: {state['user_location']}")
            if "user_input_location" in state:
                result["user_input_location"] = state["user_input_location"]
            
            # If this is a direct facility request, set service_type in state
            if decision.facility_type:
                result["service_type"] = decision.facility_type
                print(f"📍 Setting service_type to {decision.facility_type} for direct facility request")
            
            print(f"✅ Router → Next: {decision.route_to or 'END'}")
            return result
            
        except Exception as e:
            print(f"❌ Router error: {e}")
            # Fallback response
            lang = metadata.get("language", "en")
            return {
                "agent_output": self.language_responses.get(lang, self.language_responses["en"])["out_of_scope"],
                "current_agent": "router",
                "next_agent": None,
                "should_end": True,
                "metadata": {**metadata, "error": str(e)}
            }

# ============================================================
# LANGGRAPH ROUTING FUNCTION
# ============================================================
def gatekeeper_routing_decision(state: Dict[str, Any]) -> str:
    """
    Simple routing decision for LangGraph
    Returns: agent name or END
    """
    next_agent = state.get("next_agent")
    
    # Map to your agent nodes
    if next_agent == "medical_qa":
        return "medical_qa"
    elif next_agent == "triage":
        return "triage"
    elif next_agent == "mental_health":
        return "mental_health"
    elif next_agent == "rumor":
        return "rumor"
    else:
        return "END"  # Use string "END" for LangGraph

# ============================================================
# SIMPLE SINGLETON
# ============================================================
_agent_instance = None

def get_understanding_agent() -> UnderstandingAgent:
    """Get the understanding agent instance"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = UnderstandingAgent()
    return _agent_instance

def router_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph wrapper"""
    return get_understanding_agent().router_agent(state)

# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("🧪 Testing Simple Understanding Agent...")
    
    agent = UnderstandingAgent()
    
    test_cases = [
        ("Hello!", "greeting"),
        ("I have chest pain", "triage"),
        ("What is diabetes?", "medical_qa"),
        ("I feel depressed", "mental_health"),
        ("Do vaccines cause autism?", "rumor"),
        ("What's the weather?", "out_of_scope"),
        ("عندي وجع ف الصدر", "triage"),
        ("شنوة مرض السكري؟", "medical_qa")
    ]
    
    for query, expected in test_cases:
        print(f"\n{'='*60}")
        print(f"📥 Input: {query}")
        
        decision, _ = agent.process(query)
        
        status = "✅" if decision.intent.value == expected else "❌"
        print(f"{status} Expected: {expected}, Got: {decision.intent.value}")
        print(f"Confidence: {decision.confidence:.2f}")
        print(f"Route to: {decision.route_to}")
        print(f"Response: {decision.response[:60]}...")
    
    print("\n✅ Simple Understanding Agent test complete!")