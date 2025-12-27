# agents/medical_agent/agent.py
from __future__ import annotations
import os
import re
import time
import json
from typing import Dict, Any, List, Optional, TypedDict
from dataclasses import dataclass
from groq import Groq
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from duckduckgo_search import DDGS
from langdetect import detect as detect_lang
import hashlib

# 🎯 LangSmith Integration
from agents.langsmith_decorators import (
    trace_agent_node, trace_llm_call, trace_retrieval, 
    trace_tool_call, add_metadata_to_state
)

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================
CHROMA_DB_PATH = "vectorstore"
EMB_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # Load from environment variable
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"  # Or other Groq models

RETRIEVER_K = 5  # Increased for better recall
MAX_WEB_RESULTS = 6
SAFETY_FALLBACK_RETRIES = 2

TRUSTED_DOMAINS = [
    "who.int", "cdc.gov", "nih.gov", "mayoclinic.org", 
    "pubmed.ncbi.nlm.nih.gov", "ms.tn", "santetunisie.rns.tn",
    "healthline.com", "webmd.com", "emedicinehealth.com"
]

# ============================================================
# GROQ LLM WRAPPER
# ============================================================
class GroqLLMWrapper:
    """Simple wrapper for Groq API to replace Ollama"""
    
    def __init__(self, api_key: str, model: str = GROQ_MODEL, temperature: float = 0.1):
        self.client = Groq(api_key=api_key)
        self.model = model
        self.temperature = temperature
    
    @trace_llm_call("medical_agent", "groq_invoke")
    def invoke(self, prompt: str) -> str:
        """Call Groq API with the prompt"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a medical assistant providing accurate and safe information."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Groq API error: {e}")
            # Return a safe fallback response
            return "I'm currently unable to provide a detailed medical response. Please consult a healthcare professional for medical advice."

# ============================================================
# STATE MANAGEMENT (LangGraph Compatible)
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

@dataclass
class UnderstandingPayload:
    """Payload from understanding agent"""
    intent: str
    language: Optional[str]
    query: str
    keywords: List[str]
    confidence: float

# ============================================================
# CORE COMPONENTS
# ============================================================
class MedicalKnowledgeBase:
    """Enhanced knowledge base with caching and fallback strategies"""
    
    def __init__(self, path: str):
        print("🔌 Initializing Medical Knowledge Base...")
        self.embeddings = HuggingFaceEmbeddings(model_name=EMB_MODEL)
        self.vectorstore = Chroma(
            persist_directory=path,
            embedding_function=self.embeddings
        )
        self.query_cache = {}
        
    @trace_retrieval("medical_agent", "chroma_vector_db")
    def retrieve_context(self, query: str, k: int = RETRIEVER_K) -> List[str]:
        """Retrieve relevant medical context with caching"""
        # Cache key based on query hash
        cache_key = hashlib.md5(query.encode()).hexdigest()
        
        if cache_key in self.query_cache:
            return self.query_cache[cache_key]
        
        try:
            # Semantic search with metadata filtering
            docs = self.vectorstore.similarity_search_with_score(
                query, 
                k=k,
                filter={"source": {"$in": ["medical", "emergency", "first_aid"]}}
            )
            
            # Filter by relevance score threshold
            relevant_docs = [
                doc.page_content for doc, score in docs 
                if score < 0.35  # Lower score = more relevant
            ]
            
            # Fallback: broader search if nothing relevant
            if not relevant_docs:
                docs = self.vectorstore.similarity_search(query, k=k)
                relevant_docs = [doc.page_content for doc in docs]
            
            self.query_cache[cache_key] = relevant_docs
            return relevant_docs
            
        except Exception as e:
            print(f"⚠️ Knowledge base retrieval error: {e}")
            return []

class WebEvidenceRetriever:
    """Trusted web search with domain validation and ranking"""
    
    def __init__(self):
        self.trusted_domains = TRUSTED_DOMAINS
        self.domain_priority = {
            "who.int": 1.0, "cdc.gov": 0.9, "nih.gov": 0.9,
            "mayoclinic.org": 0.85, "pubmed.ncbi.nlm.nih.gov": 0.95
        }
    
    @trace_tool_call("medical_agent", "web_search_duckduckgo")
    def search_medical_info(self, query: str, max_results: int = MAX_WEB_RESULTS) -> List[Dict]:
        """Search trusted medical sources with ranking"""
        results = []
        
        try:
            # Updated to use the renamed package
            try:
                from ddgs import DDGS  # Try new package name
            except ImportError:
                from duckduckgo_search import DDGS  # Fallback to old name
            
            with DDGS() as ddgs:
                # Search with medical context
                medical_query = f"medical emergency {query} site:.org OR site:.gov"
                
                for result in ddgs.text(medical_query, max_results=max_results * 2):
                    url = result.get("href", "")
                    
                    # Validate domain trustworthiness
                    domain_trust = self._get_domain_trust(url)
                    if domain_trust > 0.6:  # Trust threshold
                        results.append({
                            "title": result.get("title", "Untitled"),
                            "snippet": result.get("body", ""),
                            "url": url,
                            "domain_trust": domain_trust,
                            "relevance_score": self._calculate_relevance(result.get("body", ""), query)
                        })
                    
                    if len(results) >= max_results:
                        break
                
                # Sort by combined score (trust * relevance)
                results.sort(key=lambda x: x["domain_trust"] * x["relevance_score"], reverse=True)
                return results[:max_results]
                
        except Exception as e:
            print(f"🌐 Web search error (rate limited): {e}")
            return []
    
    def _get_domain_trust(self, url: str) -> float:
        """Calculate domain trust score"""
        for domain, priority in self.domain_priority.items():
            if domain in url:
                return priority
        # Penalize unknown domains
        return 0.3 if any(d in url for d in [".gov", ".org", ".edu"]) else 0.1
    
    def _calculate_relevance(self, text: str, query: str) -> float:
        """Simple relevance scoring"""
        query_terms = set(query.lower().split())
        text_lower = text.lower()
        
        # Term frequency scoring
        matches = sum(1 for term in query_terms if term in text_lower)
        return min(matches / len(query_terms), 1.0) if query_terms else 0.5

class AnswerEvaluator:
    """Evaluate answer quality, safety, and completeness"""
    
    def __init__(self, llm: GroqLLMWrapper):
        self.llm = llm
    
    def evaluate_answer(self, query: str, answer: str, context: List[str]) -> Dict[str, Any]:
        """Comprehensive answer evaluation"""
        
        evaluation_prompt = f"""
        As a medical QA evaluator, assess this answer on these criteria (0-1 scale):
        
        1. SAFETY (0.3 weight): Does it avoid dangerous advice? Contains disclaimers?
        2. RELEVANCE (0.25 weight): Directly addresses the query?
        3. COMPLETENESS (0.2 weight): Covers key aspects without missing critical info?
        4. CLARITY (0.15 weight): Clear, concise, non-technical when possible?
        5. SOURCE_ALIGNMENT (0.1 weight): Consistent with provided context?
        
        QUERY: {query}
        ANSWER: {answer}
        CONTEXT: {' | '.join(context[:3])}
        
        Return JSON only: {{"safety": 0.9, "relevance": 0.8, "completeness": 0.7, 
                          "clarity": 0.85, "source_alignment": 0.9, 
                          "needs_refinement": false, "refinement_suggestions": ""}}
        """
        
        try:
            response = self.llm.invoke(evaluation_prompt).strip()
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                eval_result = json.loads(json_match.group())
                
                # Calculate overall score
                weights = {"safety": 0.3, "relevance": 0.25, 
                          "completeness": 0.2, "clarity": 0.15, 
                          "source_alignment": 0.1}
                
                overall_score = sum(
                    eval_result.get(k, 0.5) * weights.get(k, 0) 
                    for k in weights.keys()
                )
                
                eval_result["overall_score"] = round(overall_score, 3)
                return eval_result
                
        except Exception as e:
            print(f"⚠️ Evaluation error: {e}")
        
        # Fallback evaluation
        return {
            "safety": 0.7, "relevance": 0.6, "completeness": 0.5,
            "clarity": 0.6, "source_alignment": 0.5,
            "overall_score": 0.6, "needs_refinement": True,
            "refinement_suggestions": "Standard medical disclaimer added"
        }

class AnswerRefiner:
    """Refine answers based on evaluation feedback"""
    
    def __init__(self, llm: GroqLLMWrapper):
        self.llm = llm
    
    def refine_answer(self, query: str, original_answer: str, 
                     context: List[str], evaluation: Dict[str, Any]) -> str:
        """Refine answer based on evaluation feedback"""
        
        if not evaluation.get("needs_refinement", False):
            return original_answer
        
        refinement_prompt = f"""
        Refine this medical answer based on these weaknesses:
        
        Weaknesses: {evaluation.get('refinement_suggestions', 'General improvement needed')}
        
        Original Query: {query}
        
        Original Answer: {original_answer}
        
        Available Context: {' | '.join(context[:3])}
        
        Improvement Guidelines:
        1. Enhance clarity and structure
        2. Add missing safety information if needed
        3. Ensure all query aspects are addressed
        4. Maintain concise format (<120 words)
        5. Keep professional, empathetic tone
        
        Provide the refined answer only:
        """
        
        try:
            refined = self.llm.invoke(refinement_prompt).strip()
            return refined
        except:
            return original_answer  # Fallback to original

# ============================================================
# MAIN LANGGRAPH AGENT
# ============================================================
class MedicalLangGraphAgent:
    """Complete LangGraph-compatible medical agent using Groq"""
    
    def __init__(self):
        print("🏥 Initializing Medical LangGraph Agent (Groq)...")
        
        # Core components
        self.knowledge_base = MedicalKnowledgeBase(CHROMA_DB_PATH)
        self.web_retriever = WebEvidenceRetriever()
        
        # Use Groq LLM instead of Ollama
        self.llm = GroqLLMWrapper(api_key=GROQ_API_KEY, model=GROQ_MODEL, temperature=0.1)
        
        # Quality components
        self.evaluator = AnswerEvaluator(self.llm)
        self.refiner = AnswerRefiner(self.llm)
        
        # Conversation memory
        self.conversation_history = []
    
    def _determine_language(self, query: str, payload_language: Optional[str]) -> str:
        """Detect language with fallbacks"""
        if payload_language and payload_language in ["en", "fr", "ar", "aeb"]:
            return payload_language
        
        try:
            detected = detect_lang(query)
            if detected.startswith("fr"):
                return "fr"
            elif detected.startswith("ar"):
                # Check if it's Tunisian Arabic
                if any(word in query.lower() for word in ["باش", "ف", "ش", "علاه"]):
                    return "aeb"
                return "ar"
            return "en"
        except:
            return "en"
    
    def _build_medical_prompt(self, query: str, context: List[str], 
                             web_sources: List[Dict], language: str) -> str:
        """Build comprehensive medical prompt"""
        
        # Language-specific instructions
        language_prompts = {
            "en": (
                "You are 'Sahtek', an English-speaking medical emergency assistant. "
                "Your role is to provide accurate, safe medical information. "
                "Always respond in English, clearly and concisely. "
                "Include safety warnings when appropriate. "
                "Limit response to 100 words maximum."
            ),
            "fr": (
                "Tu es 'Sahtek', un assistant médical d'urgence francophone. "
                "Ton rôle est de fournir des informations médicales précises et sécurisées. "
                "Réponds toujours en français, de manière claire et concise. "
                "Inclus des avertissements de sécurité quand nécessaire. "
                "Limite ta réponse à 100 mots maximum."
            ),
            "ar": (
                "أنت 'صحتك'، مساعد طبي للطوارئ ناطق بالعربية. "
                "دورك هو تقديم معلومات طبية دقيقة وآمنة. "
                "الرد دائماً بالعربية، بوضوح وإيجاز. "
                "قم بتضمين تحذيرات السلامة عند الاقتضاء. "
                "حدد الرد بـ 100 كلمة كحد أقصى."
            ),
            "aeb": (
                "أنت 'صحتك'، مساعد طبي للطوارئ ناطق باللهجة التونسية. "
                "دورك هو تقديم معلومات طبية دقيقة وآمنة. "
                "الرد دائماً باللهجة التونسية، بوضوح وإيجاز. "
                "تحتوي على تحذيرات السلامة عند الحاجة. "
                "حدد الرد بـ 100 كلمة كحد أقصى."
            )
        }
        
        persona = language_prompts.get(language, language_prompts["en"])
        
        # Format context
        context_text = "\n".join([f"[{i+1}] {c}" for i, c in enumerate(context[:3])])
        
        # Format web sources
        web_text = ""
        if web_sources:
            web_text = "\nVerified Web Sources:\n" + "\n".join(
                [f"• {s['title']}: {s['snippet'][:150]}..." 
                 for s in web_sources[:2]]
            )
        
        prompt = f"""
        {persona}
        
        SAFETY GUIDELINES:
        1. NEVER provide dosage recommendations
        2. ALWAYS recommend professional medical consultation for serious symptoms
        3. Flag emergency situations (chest pain, difficulty breathing, etc.)
        4. Stay within the bounds of provided information
        
        RETRIEVED KNOWLEDGE:
        {context_text}
        
        {web_text}
        
        CONVERSATION HISTORY (last 2 exchanges):
        {self._format_history()}
        
        USER QUERY: {query}
        
        STRUCTURED RESPONSE FORMAT:
        1. Direct answer to the query
        2. Key points (bullet format)
        3. Safety considerations
        4. When to seek immediate help
        
        Your response:
        """
        
        return prompt
    
    def _format_history(self) -> str:
        """Format conversation history for context"""
        if not self.conversation_history or len(self.conversation_history) < 2:
            return "No relevant history."
        
        recent = self.conversation_history[-2:]
        return "\n".join([f"User: {h['user']}\nAssistant: {h['assistant']}" 
                         for h in recent])
    
    def _add_safety_disclaimer(self, answer: str, language: str) -> str:
        """Add appropriate safety disclaimer"""
        disclaimers = {
            "en": (
                "\n\n⚠️ **Safety Notice**: This is educational information only. "
                "Consult a healthcare professional immediately for serious symptoms "
                "or emergency situations."
            ),
            "fr": (
                "\n\n⚠️ **Avertissement de sécurité**: Cette information est à titre éducatif uniquement. "
                "Consultez immédiatement un professionnel de santé pour les symptômes graves "
                "ou les situations d'urgence."
            ),
            "ar": (
                "\n\n⚠️ **إشعار السلامة**: هذه المعلومات لأغراض تعليمية فقط. "
                "استشر أخصائي رعاية صحية على الفور للأعراض الخطيرة "
                "أو حالات الطوارئ."
            ),
            "aeb": (
                "\n\n⚠️ **إشعار السلامة**: هاذي المعلومات للأغراض التعليمية فقط. "
                "استشير أخصائي رعاية صحية على طول للأعراض الخطيرة "
                "أو حالات الطوارئ."
            )
        }
        
        disclaimer = disclaimers.get(language, disclaimers["en"])
        return answer + disclaimer
    
    @trace_agent_node("medical_agent", "🏥_MedicalQA_ProcessQuery")
    def process_query(self, state: MedicalAgentState) -> MedicalAgentState:
        """Main processing method for LangGraph"""
        
        # 🧹 CLEAN UP TRIAGE DATA - Reset diagnosis state when switching to medical_qa
        state["pending_questions"] = []
        state["should_end"] = False
        state["diagnosis_session_id"] = None
        state["symptoms_found"] = []
        state["diagnoses"] = []
        state["healthcare_recommendation"] = None
        
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
        
        # Step 1: Knowledge Retrieval
        print("📚 Retrieving medical knowledge...")
        kb_context = self.knowledge_base.retrieve_context(user_input)
        
        # Step 2: Web Evidence (only if KB is insufficient)
        web_sources = []
        if len(kb_context) < 2 or payload.confidence < 0.7:
            print("🌐 Searching trusted web sources...")
            web_sources = self.web_retriever.search_medical_info(user_input)
        
        # Step 3: Generate Initial Answer
        print("💭 Generating medical response...")
        prompt = self._build_medical_prompt(user_input, kb_context, web_sources, language)
        
        initial_answer = self.llm.invoke(prompt)
        initial_answer = self._add_safety_disclaimer(initial_answer, language)
        
        # Step 4: Evaluate Answer (optional, can be skipped for speed)
        print("📊 Evaluating answer quality...")
        evaluation = self.evaluator.evaluate_answer(
            user_input, initial_answer, kb_context
        )
        
        # Step 5: Refine if needed
        final_answer = initial_answer
        if evaluation.get("needs_refinement", False) and evaluation["overall_score"] < 0.75:
            print("🔧 Refining answer...")
            final_answer = self.refiner.refine_answer(
                user_input, initial_answer, kb_context, evaluation
            )
            final_answer = self._add_safety_disclaimer(final_answer, language)
        
        # Step 6: Update conversation history
        self.conversation_history.append({
            "user": user_input,
            "assistant": final_answer,
            "timestamp": time.time()
        })
        
        # Keep history manageable
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
        
        # Step 7: Update state for LangGraph avec métadonnées LangSmith
        state = add_metadata_to_state(state, "medical_agent", "retrieval", {
            "kb_docs": len(kb_context),
            "web_results": len(web_sources),
            "evaluation_score": evaluation["overall_score"],
            "language": language
        })
        
        state.update({
            "agent_output": final_answer,
            "current_agent": "medical_qa",
            "next_agent": self._determine_next_agent(user_input, final_answer),
            "medical_context": kb_context,
            "web_sources": web_sources,
            "confidence_score": evaluation["overall_score"],
            "language": language,
            "requires_refinement": evaluation.get("needs_refinement", False),
            "evaluation_result": evaluation,
            "safety_checks_passed": evaluation["safety"] > 0.8
        })
        
        return state
    
    def _determine_next_agent(self, query: str, answer: str) -> Optional[str]:
        """Determine if escalation is needed"""
        query_lower = query.lower()
        
        # Emergency keywords that require triage escalation
        emergency_keywords = [
            "chest pain", "can't breathe", "severe pain", "unconscious",
            "bleeding heavily", "heart attack", "stroke symptoms",
            "suicidal", "emergency", "urgent help"
        ]
        
        if any(keyword in query_lower for keyword in emergency_keywords):
            return "triage"
        
        # Mental health concerns
        mental_health_keywords = ["depressed", "anxious", "panic", "mental health", "suicide"]
        if any(keyword in query_lower for keyword in mental_health_keywords):
            return "mental_health"
        
        return None

# ============================================================
# LANGGRAPH NODE FUNCTION
# ============================================================
# Singleton instance
_medical_agent_instance = None

@trace_agent_node("medical_agent", "🏥_MedicalQA_Node")
def medical_qa_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node function - wraps the medical agent
    
    This is the function you'll add to your LangGraph:
    graph.add_node("medical_qa", medical_qa_agent)
    """
    global _medical_agent_instance
    
    # Initialize agent if needed
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
        safety_checks_passed=state.get("safety_checks_passed", False)
    )
    
    # Process through agent
    result_state = _medical_agent_instance.process_query(typed_state)
    
    # Convert back to regular dict
    return dict(result_state)

# ============================================================
# SIMPLE TEST
# ============================================================
if __name__ == "__main__":
    print("🧪 Testing Medical LangGraph Agent with Groq...")
    
    # Test the agent standalone
    test_queries = [
        "What are the symptoms of asthma?",
        "How to treat a fever?",
    ]
    
    agent = MedicalLangGraphAgent()
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"📥 Query: {query}")
        print('='*60)
        
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
                    "keywords": [],
                    "confidence": 0.8
                }
            },
            messages=[],
            medical_context=[],
            web_sources=[],
            confidence_score=0.0,
            language="en",
            requires_refinement=False,
            evaluation_result=None,
            safety_checks_passed=False
        )
        
        result = agent.process_query(test_state)
        
        print(f"🌐 Language: {result['language']}")
        print(f"📊 Confidence: {result['confidence_score']}")
        print(f"🔍 Sources used: {len(result['web_sources'])} web, {len(result['medical_context'])} KB")
        print(f"⚠️ Safety check: {'PASSED' if result['safety_checks_passed'] else 'FAILED'}")
        print(f"⏭️ Next agent: {result['next_agent'] or 'None'}")
        print(f"\n💬 Answer ({len(result['agent_output'])} chars):")
        print("-" * 40)
        print(result['agent_output'])
        
        time.sleep(1)  # Rate limiting for API
    
    print("\n✅ Medical LangGraph Agent test complete!")