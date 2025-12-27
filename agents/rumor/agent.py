# agents/rumor/agent.py
from __future__ import annotations
import json
import hashlib
from typing import Dict, Any, List, Optional, TypedDict
from dataclasses import dataclass
from groq import Groq
from datetime import datetime
from urllib.parse import urlparse
import requests
import time
from ddgs import DDGS
import re
import os

# 🎯 LangSmith Integration
try:
    from langsmith import traceable
except ImportError:
    # Fallback si LangSmith n'est pas installé
    def traceable(func=None, **kwargs):
        def decorator(f):
            return f
        return decorator if func is None else decorator(func)

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma
except ImportError:
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_chroma import Chroma
    except ImportError:
        HuggingFaceEmbeddings = None
        Chroma = None

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # Load from environment variable
GROQ_MODEL = "llama-3.3-70b-versatile"
API_DELAY = 1  # secondes

OPR_URL = "https://openpagerank.com/api/v1.0/getPageRank"
OPR_API_KEY = "coows44ko00wgcos8gkkwkoow0oc8socs88gs0k8"
OPR_HEADERS = {"API-OPR": OPR_API_KEY}
OPR_THRESHOLD = 6.5

CERTIFIED_DOMAINS = [
    "who.int", "cdc.gov", "nih.gov", "mayoclinic.org",
    "webmd.com", "healthline.com", "ncbi.nlm.nih.gov",
    "ms.tn", "santetunisie.rns.tn"
]

CATEGORIES = [
    "Nutrition", "Physical Activity", "Mental Health",
    "Chronic Diseases", "Infectious Diseases",
    "Preventive Medicine", "Alternative Medicine"
]

# ============================================================
# DATABASE CONFIGURATION
# ============================================================
CHROMA_DB_PATH = "agents/rumor/chroma_db"
EMB_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
JSON_DB_PATH = "health_rumors_db.json"

# ============================================================
# RUMOR DATABASE MANAGEMENT
# ============================================================
class RumorDatabase:
    """Gère la base de données persistante des rumeurs vérifiées"""
    
    def __init__(self, json_path: str = JSON_DB_PATH, chroma_path: str = CHROMA_DB_PATH):
        self.json_path = json_path
        self.chroma_path = chroma_path
        self.database = {
            "Nutrition": [],
            "Physical Activity": [],
            "Mental Health": [],
            "Chronic Diseases": [],
            "Infectious Diseases": [],
            "Preventive Medicine": [],
            "Alternative Medicine": []
        }
        
        # Initialiser Chroma si disponible
        self.embeddings = None
        self.vectorstore = None
        if HuggingFaceEmbeddings and Chroma:
            try:
                print("🔌 Initializing Rumor Chroma Database...")
                os.makedirs(chroma_path, exist_ok=True)
                self.embeddings = HuggingFaceEmbeddings(model_name=EMB_MODEL)
                self.vectorstore = Chroma(
                    persist_directory=chroma_path,
                    embedding_function=self.embeddings,
                    collection_name="health_rumors"
                )
                print("✅ Rumor Chroma Database initialized")
            except Exception as e:
                print(f"⚠️ Warning: Chroma DB initialization failed: {e}")
                self.vectorstore = None
        
        # Charger la base JSON
        self.load_json_database()
    
    def load_json_database(self):
        """Charge la base de données JSON"""
        try:
            if os.path.exists(self.json_path):
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    self.database = json.load(f)
                print(f"📂 Database loaded: {self.json_path}")
            else:
                print(f"📝 Creating new database: {self.json_path}")
                self.save_json_database()
        except Exception as e:
            print(f"⚠️ Error loading database: {e}")
    
    def save_json_database(self):
        """Sauvegarde la base de données JSON"""
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(self.database, f, indent=2, ensure_ascii=False)
            print(f"💾 Database saved: {self.json_path}")
        except Exception as e:
            print(f"❌ Error saving database: {e}")
    
    def find_rumor(self, claim: str, category: str) -> Optional[Dict]:
        """Cherche une rumeur dans la base"""
        claim_lower = claim.lower().strip()
        for rumor in self.database.get(category, []):
            if rumor.get("claim", "").lower().strip() == claim_lower:
                return rumor
        return None
    
    def check_if_recently_verified(self, claim: str, category: str, days: int = 3) -> bool:
        """Vérifie si une rumeur a été vérifiée récemment"""
        existing = self.find_rumor(claim, category)
        if existing:
            last_updated = datetime.fromisoformat(existing.get("last_updated", ""))
            days_since = (datetime.now() - last_updated).days
            return days_since <= days
        return False
    
    def save_verification_result(self, rumor_claim: str, category: str, verdict: str, 
                                 score: float, credibility_percentage: float, 
                                 process_details: Dict, verification_result: Dict):
        """Sauvegarde le résultat d'une vérification"""
        existing_rumor = self.find_rumor(rumor_claim, category)
        
        verification_entry = {
            "timestamp": datetime.now().isoformat(),
            "score": score,
            "credibility_percentage": credibility_percentage,
            "verdict": verdict,
            "official_sources": len(verification_result.get("official_sources", [])),
            "web_sources": len(verification_result.get("web_sources", [])),
            "sources": verification_result.get("official_sources", [])[:3]
        }
        
        if existing_rumor:
            print(f"📝 Updating existing rumor...")
            existing_rumor["last_updated"] = datetime.now().isoformat()
            existing_rumor["verdict"] = verdict
            existing_rumor["score"] = score
            existing_rumor["credibility_percentage"] = credibility_percentage
            existing_rumor["verification_count"] = existing_rumor.get("verification_count", 1) + 1
            if "verifications" not in existing_rumor:
                existing_rumor["verifications"] = []
            existing_rumor["verifications"].append(verification_entry)
        else:
            print(f"✅ Adding new rumor to database...")
            new_entry = {
                "claim": rumor_claim,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "verdict": verdict,
                "score": score,
                "credibility_percentage": credibility_percentage,
                "verification_count": 1,
                "verifications": [verification_entry],
                "process": process_details
            }
            self.database[category].append(new_entry)
        
        # Sauvegarder immédiatement
        self.save_json_database()
        
        # Ajouter à Chroma DB si disponible
        if self.vectorstore:
            try:
                doc_id = hashlib.md5(f"{rumor_claim}_{category}".encode()).hexdigest()
                metadata = {
                    "claim": rumor_claim,
                    "category": category,
                    "verdict": verdict,
                    "credibility": credibility_percentage,
                    "timestamp": datetime.now().isoformat()
                }
                self.vectorstore.add_texts(
                    texts=[f"{rumor_claim} - {verdict} ({credibility_percentage}%)"],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
                print(f"✅ Added to Chroma DB")
            except Exception as e:
                print(f"⚠️ Warning: Could not add to Chroma: {e}")
    
    def get_similar_rumors(self, claim: str, k: int = 3) -> List[Dict]:
        """Trouve les rumeurs similaires dans Chroma"""
        if not self.vectorstore:
            return []
        
        try:
            results = self.vectorstore.similarity_search(claim, k=k)
            return results
        except Exception as e:
            print(f"⚠️ Warning: Could not search Chroma: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """Retourne les statistiques de la base"""
        stats = {
            "total_rumors": 0,
            "by_category": {},
            "by_verdict": {
                "CREDIBLE": 0,
                "PARTIALLY_CREDIBLE": 0,
                "QUESTIONABLE": 0,
                "NOT_CREDIBLE": 0
            }
        }
        
        for category, rumors in self.database.items():
            stats["by_category"][category] = len(rumors)
            stats["total_rumors"] += len(rumors)
            for rumor in rumors:
                verdict = rumor.get("verdict", "")
                if verdict in stats["by_verdict"]:
                    stats["by_verdict"][verdict] += 1
        
        return stats

# ============================================================
# STATE MANAGEMENT (LangGraph Compatible)
# ============================================================
class RumorAgentState(TypedDict):
    """Enhanced state for rumor verification agent"""
    user_input: str
    agent_output: Optional[str]
    current_agent: str
    next_agent: Optional[str]
    metadata: Dict[str, Any]
    messages: List[Dict[str, str]]
    
    # Rumor-specific fields
    rumor: str
    category: str
    verdict: str
    score: int
    credibility_percentage: float
    official_sources: List[Dict[str, str]]
    web_sources: List[Dict[str, str]]
    verification_details: Optional[Dict[str, Any]]
    language: str
    safety_checks_passed: bool

# ============================================================
# GROQ LLM WRAPPER
# ============================================================
class GroqLLMWrapper:
    """Wrapper pour Groq API"""
    
    def __init__(self, api_key: str, model: str = GROQ_MODEL, temperature: float = 0.0):
        self.client = Groq(api_key=api_key)
        self.model = model
        self.temperature = temperature  # 0.0 pour plus de déterminisme
    
    @traceable(run_type="llm", name="🔍_Rumor_LLM_Call")
    def invoke(self, prompt: str) -> str:
        """Appel Groq API"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error: {str(e)}"

# ============================================================
# CORE COMPONENTS
# ============================================================
class SourceCredibilityEvaluator:
    """Évalue la crédibilité des sources via PageRank"""
    
    def __init__(self):
        self.trusted_domains = CERTIFIED_DOMAINS
        self.domain_priority = {
            "who.int": 1.0, "cdc.gov": 0.95, "nih.gov": 0.9,
            "mayoclinic.org": 0.85, "ncbi.nlm.nih.gov": 0.95
        }
    
    def extract_domain(self, url: str) -> str:
        """Extrait le domaine d'une URL"""
        parsed = urlparse(url)
        return parsed.netloc or url
    
    @traceable(name="🔍_Rumor_GetPageRankScore")
    def get_opr_score(self, domain: str) -> float:
        """Récupère le score OpenPageRank"""
        try:
            resp = requests.get(
                OPR_URL,
                params={"domains[]": domain},
                headers=OPR_HEADERS,
                timeout=5
            )
            resp.raise_for_status()
            data = resp.json().get("response", [])
            if not data:
                return 0.0
            return float(data[0].get("page_rank_decimal", 0.0))
        except Exception as e:
            return 0.0
    
    def is_certified_domain(self, domain: str) -> bool:
        """Vérifie si le domaine est certifié"""
        return any(cert in domain for cert in self.trusted_domains)
    
    @traceable(name="🔍_Rumor_EvaluateCredibility")
    def evaluate_source(self, url: str) -> Dict[str, Any]:
        """Évalue la crédibilité d'une source"""
        domain = self.extract_domain(url)
        
        if self.is_certified_domain(domain):
            return {
                "domain": domain,
                "is_certified": True,
                "opr_score": 10.0,
                "credibility_multiplier": 1.0,
                "status": "CERTIFIED"
            }
        
        opr_score = self.get_opr_score(domain)
        
        if opr_score >= OPR_THRESHOLD:
            credibility_multiplier = 0.9
            status = "RELIABLE"
        elif opr_score >= 5.0:
            credibility_multiplier = 0.6
            status = "MODERATE"
        else:
            credibility_multiplier = 0.3
            status = "LOW_TRUST"
        
        return {
            "domain": domain,
            "is_certified": False,
            "opr_score": opr_score,
            "credibility_multiplier": credibility_multiplier,
            "status": status
        }

class WebEvidenceSearcher:
    """Recherche des preuves sur le web"""
    
    @traceable(name="🔍_Rumor_SearchCertified")
    def search_certified_sources(self, query: str, max_results: int = 5) -> List[Dict]:
        """Recherche dans les sources certifiées"""
        results = []
        sites = [
            "site:who.int", "site:cdc.gov", "site:nih.gov", "site:mayoclinic.org"
        ]
        
        try:
            with DDGS() as ddgs:
                for site in sites:
                    search_query = f"{query} {site}"
                    for result in ddgs.text(search_query, max_results=2):
                        results.append(result)
        except Exception as e:
            pass
        
        return results[:max_results]
    
    @traceable(name="🔍_Rumor_SearchWeb")
    def search_web(self, query: str, max_results: int = 5) -> List[Dict]:
        """Recherche générale sur le web"""
        results = []
        
        try:
            with DDGS() as ddgs:
                for result in ddgs.text(query, max_results=max_results):
                    results.append(result)
        except Exception as e:
            pass
        
        return results

class RumorCategoryDetector:
    """Détecte la catégorie d'une rumeur"""
    
    def __init__(self, llm: GroqLLMWrapper):
        self.llm = llm
    
    @traceable(name="🔍_Rumor_DetectCategory")
    def detect_category(self, rumor: str) -> str:
        """Détecte la catégorie via LLM"""
        categories_str = ", ".join(CATEGORIES)
        
        prompt = f"""Classify this health claim into ONE category.
        
Claim: "{rumor}"

Categories: {categories_str}

Respond with ONLY the category name, nothing else."""
        
        print("   📤 Envoi au LLM pour classification...")
        result = self.llm.invoke(prompt).strip()
        
        if result not in CATEGORIES:
            print(f"   ⚠️ Catégorie non reconnue '{result}', utilisation de 'Physical Activity'")
            return "Physical Activity"
        
        print(f"   ✅ Catégorie reconnue: {result}")
        return result

class RumorVerifier:
    """Vérifie les rumeurs de santé"""
    
    def __init__(self, llm: GroqLLMWrapper):
        self.llm = llm
        self.credibility_evaluator = SourceCredibilityEvaluator()
        self.searcher = WebEvidenceSearcher()
        self.analysis_cache = {}  # Cache des analyses pour éviter les appels redondants
        self.database = RumorDatabase()  # Base de données persistante
    
    def clean_json_response(self, txt: str) -> str:
        """Nettoie les réponses JSON du LLM"""
        if "```json" in txt:
            txt = txt.split("```json")[1].split("```")[0]
        elif "```" in txt:
            parts = txt.split("```")
            if len(parts) >= 2:
                txt = parts[1]
        
        txt = txt.strip()
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', txt, re.DOTALL)
        if json_match:
            txt = json_match.group(0)
        
        return txt
    
    @traceable(name="🔍_Rumor_AnalyzeSources")
    def analyze_sources(self, rumor: str, results: List[Dict], source_type: str) -> Dict[str, Any]:
        """Analyse les résultats de recherche"""
        if not results:
            return {
                "score": 0,
                "resume": "No sources found",
                "source_evaluations": []
            }
        
        # Créer une clé de cache basée sur la rumeur et le type de source
        cache_key = hashlib.md5(f"{rumor}_{source_type}".encode()).hexdigest()
        
        if cache_key in self.analysis_cache:
            print(f"      ♻️  Résultat en cache trouvé")
            cached = self.analysis_cache[cache_key].copy()
            print(f"      ✅ Analyse reçue (cache): score = {cached.get('score', 0)}")
            return cached
        
        print(f"      📋 Évaluation de la crédibilité des sources...")
        # Évaluer chaque source
        source_evaluations = []
        for i, result in enumerate(results[:3], 1):
            url = result.get("href") or result.get("url", "")
            if url:
                eval_result = self.credibility_evaluator.evaluate_source(url)
                source_evaluations.append(eval_result)
                status = eval_result.get("status", "UNKNOWN")
                print(f"         Source {i}: {status} (PageRank: {eval_result.get('opr_score', 0):.1f}/10)")
        
        # Préparer le texte pour le LLM
        resume_textes = ""
        for i, r in enumerate(results[:3], 1):
            title = r.get("title", "N/A")[:100]
            body = r.get("body", "N/A")[:200]
            resume_textes += f"{i}. {title}\n{body}\n\n"
        
        score_max = 50 if source_type == "certified" else 30
        avg_credibility = sum(s.get("credibility_multiplier", 0.5) for s in source_evaluations) / len(source_evaluations) if source_evaluations else 0.5
        
        # Prompt amélioré avec directives de cohérence
        prompt = f"""You are a fact-checker analyzing health claims. Provide a coherent analysis where the summary directly reflects the credibility score.

CLAIM: "{rumor}"

SOURCES ({source_type}):
{resume_textes}

SCORING GUIDELINES:
- 0-15 points: Clearly NOT credible (no supporting evidence, contradicted by sources)
- 16-30 points: LOW credibility (weak evidence, mostly unsupported)
- 31-45 points: MODERATE credibility (some supporting evidence, partially verified)
- 46-50 points: HIGH credibility (strong evidence, well supported)

SOURCE CREDIBILITY LEVEL: {avg_credibility:.2f}/1.0 ({"HIGH" if avg_credibility >= 0.8 else "MODERATE" if avg_credibility >= 0.5 else "LOW"})

Based on the sources provided, rate this claim's credibility (0-{score_max}) and provide a one-sentence explanation that DIRECTLY reflects your score.

IMPORTANT: Your explanation MUST be consistent with the score you give.

Respond ONLY with valid JSON, no other text:
{{"score": 0, "resume": "explanation that matches the score"}}"""
        
        print(f"      📤 Envoi au LLM pour analyse...")
        time.sleep(API_DELAY)
        response = self.llm.invoke(prompt)
        
        try:
            txt = self.clean_json_response(response)
            result = json.loads(txt)
            score = result.get('score', 0)
            resume = result.get('resume', 'Analysis complete')
            
            # Vérifier la cohérence score/résumé
            print(f"      ✅ Analyse reçue: score = {score}/{score_max}")
            
            # Valider le score
            if score < 0:
                score = 0
            elif score > score_max:
                score = score_max
            
            result["score"] = score
            result["resume"] = resume
            
        except Exception as e:
            print(f"      ⚠️ Erreur de parsing JSON: {str(e)}")
            # Fournir une analyse par défaut cohérente
            result = {
                "score": int(score_max * 0.4),
                "resume": "Unable to fully analyze due to parsing error. Review sources manually."
            }
        
        # Ajuster le score selon la crédibilité des sources
        original_score = result.get("score", 0)
        if source_evaluations and avg_credibility < 1.0:
            adjusted_score = original_score * avg_credibility
            result["original_score"] = original_score
            result["score"] = round(adjusted_score, 2)
            result["credibility_adjustment"] = avg_credibility
            print(f"      📊 Score ajusté: {original_score} × {avg_credibility:.2f} = {result['score']:.2f}")
        
        result["source_evaluations"] = source_evaluations
        
        # Mettre en cache le résultat
        self.analysis_cache[cache_key] = result.copy()
        
        return result
    
    @traceable(run_type="chain", name="🔍_Rumor_VerifyRumor")
    def verify_rumor(self, rumor: str, category: str) -> Dict[str, Any]:
        """Vérifie une rumeur complètement avec gestion de base de données"""
        
        # Vérifier si la rumeur a été vérifiée récemment
        if self.database.check_if_recently_verified(rumor, category, days=3):
            print("   ♻️  Cette rumeur a été vérifiée récemment")
            existing = self.database.find_rumor(rumor, category)
            if existing:
                days_since = (datetime.now() - datetime.fromisoformat(existing.get('last_updated'))).days
                print(f"   ✅ Résultat du cache (il y a {days_since} jours)")
                
                # Mapper les anciens verdicts au nouveaux
                verdict_mapping = {
                    "HIGH CREDIBILITY": "CREDIBLE",
                    "MODERATE CREDIBILITY": "PARTIALLY_CREDIBLE",
                    "LOW CREDIBILITY": "QUESTIONABLE",
                    "NOT CREDIBLE": "NOT_CREDIBLE",
                    "CREDIBLE": "CREDIBLE",
                    "PARTIALLY_CREDIBLE": "PARTIALLY_CREDIBLE",
                    "QUESTIONABLE": "QUESTIONABLE",
                    "NOT_CREDIBLE": "NOT_CREDIBLE"
                }
                
                verdict = verdict_mapping.get(existing.get("verdict", "QUESTIONABLE"), "QUESTIONABLE")
                
                return {
                    "rumor": rumor,
                    "total_score": existing.get("score", 0),
                    "max_score": 50,
                    "verdict": verdict,
                    "credibility_percentage": existing.get("credibility_percentage", 0.0),
                    "official_sources": [],
                    "web_sources": [],
                    "verification_details": {},
                    "from_cache": True
                }
        
        results = {
            "rumor": rumor,
            "total_score": 0,
            "max_score": 50,
            "verdict": "UNKNOWN",
            "credibility_percentage": 0.0,
            "official_sources": [],
            "web_sources": [],
            "verification_details": {},
            "from_cache": False
        }
        
        # 1. Recherche dans sources certifiées
        print("   🔍 Recherche dans sources certifiées (WHO, CDC, NIH, etc.)...")
        official_results = self.searcher.search_certified_sources(rumor)
        results["official_sources"] = official_results
        
        official_analysis = None
        if official_results:
            print(f"   ✅ {len(official_results)} source(s) certifiée(s) trouvée(s)")
            print("   📊 Analyse des sources officielles...")
            official_analysis = self.analyze_sources(rumor, official_results, "certified")
            results["total_score"] += official_analysis.get("score", 0)
            results["verification_details"]["official"] = official_analysis
            print(f"   ✅ Score officiel: {official_analysis.get('score', 0)}/50")
        else:
            print("   ⚠️ Aucune source certifiée trouvée")
        
        # 2. Recherche web générale si peu de sources officielles
        if not official_results or len(official_results) < 2:
            print("   🌐 Recherche sur le web (sources générales)...")
            web_results = self.searcher.search_web(rumor, max_results=5)
            results["web_sources"] = web_results
            
            if web_results:
                print(f"   ✅ {len(web_results)} source(s) web trouvée(s)")
                print("   📊 Analyse des sources web...")
                web_analysis = self.analyze_sources(rumor, web_results, "web")
                results["total_score"] += web_analysis.get("score", 0) * 0.6  # 60% du score pour web
                results["verification_details"]["web"] = web_analysis
                print(f"   ✅ Score web: {web_analysis.get('score', 0)} * 0.6 = {web_analysis.get('score', 0) * 0.6:.1f}")
            else:
                print("   ⚠️ Aucune source web trouvée")
        
        # 3. Calcul du verdict
        print("   🎯 Calcul du verdict...")
        percentage = (results["total_score"] / results["max_score"]) * 100
        results["credibility_percentage"] = round(percentage, 2)
        
        if percentage >= 75:
            results["verdict"] = "CREDIBLE"
        elif percentage >= 50:
            results["verdict"] = "PARTIALLY_CREDIBLE"
        elif percentage >= 25:
            results["verdict"] = "QUESTIONABLE"
        else:
            results["verdict"] = "NOT_CREDIBLE"
        
        print(f"   ✅ Verdict final: {results['verdict']} ({percentage:.1f}%)")
        
        # 4. Sauvegarder dans la base de données
        print("   💾 Sauvegarde dans la base de données...")
        process_details = {
            "rumor": rumor,
            "timestamp": datetime.now().isoformat(),
            "steps": []
        }
        
        self.database.save_verification_result(
            rumor_claim=rumor,
            category=category,
            verdict=results["verdict"],
            score=results["total_score"],
            credibility_percentage=results["credibility_percentage"],
            process_details=process_details,
            verification_result=results
        )
        print("   ✅ Sauvegarde complétée")
        
        return results

# ============================================================
# MAIN LANGGRAPH AGENT
# ============================================================
class RumorLangGraphAgent:
    """Agent LangGraph complet pour la vérification de rumeurs"""
    
    def __init__(self):
        print("🔍 Initializing Rumor Verification Agent...")
        
        # Core components
        self.llm = GroqLLMWrapper(api_key=GROQ_API_KEY, model=GROQ_MODEL)
        self.detector = RumorCategoryDetector(self.llm)
        self.verifier = RumorVerifier(self.llm)
        
        # Conversation memory
        self.conversation_history = []
    
    def process_query(self, state: RumorAgentState) -> RumorAgentState:
        """Traite une requête de vérification de rumeur"""
        
        # 🧹 CLEAN UP TRIAGE DATA - Reset diagnosis state when switching to rumor
        state["pending_questions"] = []
        state["should_end"] = False
        state["diagnosis_session_id"] = None
        state["symptoms_found"] = []
        state["diagnoses"] = []
        state["healthcare_recommendation"] = None
        
        user_input = state.get("user_input", "").strip()
        
        if not user_input:
            state["agent_output"] = "❌ Veuillez fournir une rumeur à vérifier."
            state["current_agent"] = "rumor"
            state["safety_checks_passed"] = False
            return state
        
        try:
            print("\n" + "="*70)
            print("🔍 DÉMARRAGE DE LA VÉRIFICATION DE RUMEUR")
            print("="*70)
            print(f"📝 Rumeur: {user_input}\n")
            
            # 1. Détecter la catégorie
            print("🔄 Étape 1/4: Détection de la catégorie...")
            category = self.detector.detect_category(user_input)
            print(f"✅ Catégorie détectée: {category}\n")
            state["category"] = category
            
            # 2. Vérifier la rumeur
            print("🔄 Étape 2/4: Recherche des sources...")
            verification_result = self.verifier.verify_rumor(user_input, category)
            print(f"✅ Recherche complétée")
            print(f"   - Sources officielles trouvées: {len(verification_result.get('official_sources', []))}")
            print(f"   - Sources web trouvées: {len(verification_result.get('web_sources', []))}\n")
            
            # 3. Construire la réponse
            print("🔄 Étape 3/4: Analyse des sources...")
            verdict = verification_result["verdict"]
            score = verification_result["total_score"]
            percentage = verification_result["credibility_percentage"]
            
            state["rumor"] = user_input
            state["verdict"] = verdict
            state["score"] = int(score)
            state["credibility_percentage"] = percentage
            state["official_sources"] = verification_result.get("official_sources", [])
            state["web_sources"] = verification_result.get("web_sources", [])
            state["verification_details"] = verification_result.get("verification_details", {})
            
            print(f"✅ Analyse complétée")
            print(f"   - Score obtenu: {score}/{verification_result.get('max_score', 50)}")
            print(f"   - Crédibilité: {percentage}%\n")
            
            # 4. Formater la réponse
            print("🔄 Étape 4/4: Génération du rapport final...\n")
            
            verdict_emoji = {
                "CREDIBLE": "✅",
                "PARTIALLY_CREDIBLE": "⚠️",
                "QUESTIONABLE": "❓",
                "NOT_CREDIBLE": "❌"
            }.get(verdict, "❓")
            
            verdict_text = {
                "CREDIBLE": "Cette rumeur est CRÉDIBLE selon les sources",
                "PARTIALLY_CREDIBLE": "Cette rumeur est PARTIELLEMENT CRÉDIBLE",
                "QUESTIONABLE": "Cette rumeur est QUESTIONNABLE",
                "NOT_CREDIBLE": "Cette rumeur est NON CRÉDIBLE"
            }.get(verdict, "Verdict inconnu")
            
            # Construction du paragraphe complet
            output = f"""{verdict_emoji} **VERDICT FINAL**

{verdict_text}. Après une analyse approfondie avec un score de crédibilité de {percentage}%, voici ce que nous avons trouvé sur: "{user_input}"

📊 **Score de crédibilité**: {percentage}% ({int(score)}/{verification_result.get('max_score', 50)} points)
📁 **Catégorie**: {category}
⏱️ **Date de vérification**: {datetime.now().strftime('%d/%m/%Y à %H:%M')}

"""
            
            # Ajouter les sources officielles
            if state["official_sources"]:
                output += f"🏛️ **Sources officielles consultées** ({len(state['official_sources'])} source{'s' if len(state['official_sources']) > 1 else ''}):\n"
                for i, source in enumerate(state["official_sources"][:3], 1):
                    title = source.get("title", "Sans titre")[:60]
                    url = source.get("href") or source.get("url", "URL indisponible")
                    output += f"   {i}. {title}\n      🔗 {url}\n"
                output += "\n"
            
            # Ajouter les sources web
            if state["web_sources"]:
                output += f"🌐 **Sources web consultées** ({len(state['web_sources'])} source{'s' if len(state['web_sources']) > 1 else ''}):\n"
                for i, source in enumerate(state["web_sources"][:3], 1):
                    title = source.get("title", "Sans titre")[:60]
                    url = source.get("href") or source.get("url", "URL indisponible")
                    output += f"   {i}. {title}\n      🔗 {url}\n"
                output += "\n"
            
            # Ajouter les détails d'analyse
            if state["verification_details"]:
                if "official" in state["verification_details"]:
                    analysis = state["verification_details"]["official"]
                    output += f"📋 **Analyse des sources officielles**: {analysis.get('resume', 'N/A')}\n"
                if "web" in state["verification_details"]:
                    analysis = state["verification_details"]["web"]
                    output += f"📋 **Analyse des sources web**: {analysis.get('resume', 'N/A')}\n"
            
            output += f"\n⚠️ **Avertissement**: Cette vérification est basée sur une analyse automatisée. Consultez un professionnel de santé pour des conseils médicaux."
            
            state["agent_output"] = output
            state["current_agent"] = "rumor"
            state["safety_checks_passed"] = True
            
            # Ajouter à l'historique
            self.conversation_history.append({
                "user": user_input,
                "assistant": output,
                "verdict": verdict,
                "percentage": percentage
            })
            
            print("✅ Rapport généré avec succès!\n")
            print("="*70)
            print(output)
            print("="*70 + "\n")
            
        except Exception as e:
            print(f"\n❌ ERREUR: {str(e)}\n")
            state["agent_output"] = f"❌ Erreur lors de la vérification: {str(e)}"
            state["current_agent"] = "rumor"
            state["safety_checks_passed"] = False
        
        return state

# ============================================================
# LANGGRAPH NODE FUNCTION
# ============================================================
_rumor_agent_instance = None

def rumor_verification_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node function - wraps the rumor verification agent
    """
    global _rumor_agent_instance
    
    # Initialize agent if needed
    if _rumor_agent_instance is None:
        _rumor_agent_instance = RumorLangGraphAgent()
        _rumor_agent_instance = RumorLangGraphAgent()
    
    # Convert state to typed dict format
    typed_state = RumorAgentState(
        user_input=state.get("user_input", ""),
        agent_output=state.get("agent_output"),
        current_agent=state.get("current_agent", "rumor"),
        next_agent=state.get("next_agent"),
        metadata=state.get("metadata", {}),
        messages=state.get("messages", []),
        rumor=state.get("rumor", ""),
        category=state.get("category", ""),
        verdict=state.get("verdict", ""),
        score=state.get("score", 0),
        credibility_percentage=state.get("credibility_percentage", 0.0),
        official_sources=state.get("official_sources", []),
        web_sources=state.get("web_sources", []),
        verification_details=state.get("verification_details"),
        language=state.get("language", "en"),
        safety_checks_passed=state.get("safety_checks_passed", False)
    )
    
    # Process through agent
    result_state = _rumor_agent_instance.process_query(typed_state)
    
    # Convert back to regular dict
    return dict(result_state)

# ============================================================
# SIMPLE TEST
# ============================================================
if __name__ == "__main__":
    print("🧪 Testing Rumor Verification Agent...")
    
    test_rumors = [
        "Drinking lemon water every morning helps detox the body",
        "Vitamin C can cure the common cold",
    ]
    
    agent = RumorLangGraphAgent()
    
    for rumor in test_rumors:
        print(f"\n📝 Vérification: {rumor}")
        state = RumorAgentState(
            user_input=rumor,
            agent_output=None,
            current_agent="rumor",
            next_agent=None,
            metadata={},
            messages=[],
            rumor="",
            category="",
            verdict="",
            score=0,
            credibility_percentage=0.0,
            official_sources=[],
            web_sources=[],
            verification_details=None,
            language="en",
            safety_checks_passed=False
        )
        
        result = agent.process_query(state)
        print(f"✅ Résultat:\n{result.get('agent_output', '')}")
    
    print("\n✅ Test complete!")
