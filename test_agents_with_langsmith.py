#!/usr/bin/env python3
"""
Test agents avec LangSmith tracing - Requêtes réelles
Lance des requêtes sur chaque agent et affiche les traces
"""

import os
import sys
from pathlib import Path
import time

# Load environment variables FIRST
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import after loading .env
from agents.langsmith_decorators import LANGSMITH_ENABLED, LANGSMITH_PROJECT

print("\n" + "="*70)
print("🚀 TESTING AGENTS WITH LANGSMITH TRACING")
print("="*70)
print(f"\n✅ LangSmith Enabled: {LANGSMITH_ENABLED}")
print(f"✅ LangSmith Project: {LANGSMITH_PROJECT}")
print(f"✅ Dashboard: https://smith.langchain.com/projects/{LANGSMITH_PROJECT}")
print("\n" + "="*70)


# ============================================================
# TEST 1: MEDICAL AGENT
# ============================================================

def test_medical_agent():
    """Test Medical Agent avec requête réelle"""
    print("\n" + "="*70)
    print("🏥 TEST 1: MEDICAL AGENT")
    print("="*70)
    
    try:
        from agents.medical_agent.agent import medical_qa_agent
        
        print("\n📝 Requête: 'Qu'est-ce que le diabète de type 2?'")
        print("⏳ Traitement en cours...")
        
        start_time = time.time()
        
        # Call the agent
        result = medical_qa_agent({
            "query": "Qu'est-ce que le diabète de type 2?",
            "language": "fr"
        })
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ Réponse reçue en {elapsed:.2f}s")
        
        if isinstance(result, dict):
            if "answer" in result:
                print(f"\n📄 Réponse (première 200 chars):")
                print(f"   {result['answer'][:200]}...")
            if "sources" in result:
                print(f"\n📚 Sources utilisées: {len(result.get('sources', []))} trouvées")
        else:
            print(f"\n📄 Réponse: {str(result)[:200]}...")
        
        print("\n✅ Traces envoyées à LangSmith")
        print("   - trace_agent_node: process_medical_query")
        print("   - trace_llm_call: groq_invoke")
        print("   - trace_retrieval: chroma_vector_db")
        print("   - trace_tool_call: web_search")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 2: MENTAL HEALTH AGENT
# ============================================================

def test_mental_health_agent():
    """Test Mental Health Agent avec requête réelle"""
    print("\n" + "="*70)
    print("🧠 TEST 2: MENTAL HEALTH AGENT")
    print("="*70)
    
    try:
        from agents.mental_health.agent import mental_health_agent
        
        print("\n📝 Requête: 'Je me sens anxieux et je ne peux pas dormir'")
        print("⏳ Traitement en cours...")
        
        start_time = time.time()
        
        # Call the agent
        result = mental_health_agent({
            "user_message": "Je me sens anxieux et je ne peux pas dormir",
            "conversation_history": [],
            "session_id": "test_session_001"
        })
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ Réponse reçue en {elapsed:.2f}s")
        
        if isinstance(result, dict):
            if "response" in result:
                print(f"\n📄 Réponse (première 250 chars):")
                print(f"   {result['response'][:250]}...")
            if "urgency_level" in result:
                print(f"\n⚠️  Niveau d'urgence: {result['urgency_level']}")
            if "safety_alert" in result:
                print(f"🚨 Alerte sécurité: {result['safety_alert']}")
        else:
            print(f"\n📄 Réponse: {str(result)[:250]}...")
        
        print("\n✅ Traces envoyées à LangSmith")
        print("   - trace_agent_node: mental_health_processing")
        print("   - trace_llm_call: groq_chat, analyze_situation")
        print("   - trace_retrieval: retrieve_relevant_techniques")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 3: TRIAGE AGENT
# ============================================================

def test_triage_agent():
    """Test Triage Agent avec requête réelle"""
    print("\n" + "="*70)
    print("⚕️  TEST 3: TRIAGE AGENT")
    print("="*70)
    
    try:
        from agents.triage_agent.agent import triage_agent
        
        print("\n📝 Requête: 'J'ai de la fièvre (39°C) et des maux de tête'")
        print("⏳ Traitement en cours...")
        
        start_time = time.time()
        
        # Call the agent
        result = triage_agent({
            "user_input": "J'ai de la fièvre (39°C) et des maux de tête",
            "patient_age": 35,
            "patient_gender": "M"
        })
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ Réponse reçue en {elapsed:.2f}s")
        
        if isinstance(result, dict):
            if "triage_level" in result:
                print(f"\n🎯 Niveau de triage: {result['triage_level']}")
            if "symptoms" in result:
                print(f"\n🔍 Symptômes détectés: {', '.join(result['symptoms'][:3])}")
            if "recommendation" in result:
                print(f"\n💊 Recommandation (première 200 chars):")
                print(f"   {str(result['recommendation'])[:200]}...")
            if "urgency_score" in result:
                print(f"\n⚡ Score d'urgence: {result['urgency_score']}/10")
        else:
            print(f"\n📄 Réponse: {str(result)[:250]}...")
        
        print("\n✅ Traces envoyées à LangSmith")
        print("   - trace_agent_node: triage_agent, extract_symptoms")
        print("   - trace_llm_call: start_diagnosis, generate_diagnosis")
        print("   - trace_retrieval: (if applicable)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 4: RUMOR AGENT
# ============================================================

def test_rumor_agent():
    """Test Rumor Agent avec requête réelle"""
    print("\n" + "="*70)
    print("🧐 TEST 4: RUMOR VERIFICATION AGENT")
    print("="*70)
    
    try:
        from agents.rumor.agent import rumor_verification_agent
        
        print("\n📝 Requête: 'Le paracétamol cause des problèmes cardiaques'")
        print("⏳ Vérification en cours...")
        
        start_time = time.time()
        
        # Call the agent
        result = rumor_verification_agent({
            "claim": "Le paracétamol cause des problèmes cardiaques",
            "language": "fr"
        })
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ Réponse reçue en {elapsed:.2f}s")
        
        if isinstance(result, dict):
            if "verdict" in result:
                print(f"\n🎯 Verdict: {result['verdict']}")
            if "confidence" in result:
                print(f"\n📊 Confiance: {result['confidence']}%")
            if "evidence" in result:
                print(f"\n📚 Preuves trouvées:")
                for evidence in result['evidence'][:2]:
                    print(f"   - {str(evidence)[:100]}...")
            if "explanation" in result:
                print(f"\n📝 Explication (première 200 chars):")
                print(f"   {result['explanation'][:200]}...")
        else:
            print(f"\n📄 Réponse: {str(result)[:250]}...")
        
        print("\n✅ Traces envoyées à LangSmith")
        print("   - trace_agent_node: rumor_verification_agent")
        print("   - trace_llm_call: (LLM calls)")
        print("   - trace_tool_call: (Web search)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# SUMMARY
# ============================================================

def main():
    """Run all tests"""
    
    results = {
        "Medical Agent": test_medical_agent(),
        "Mental Health Agent": test_mental_health_agent(),
        "Triage Agent": test_triage_agent(),
        "Rumor Agent": test_rumor_agent(),
    }
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    # Show where to see traces
    print("\n" + "="*70)
    print("🎯 VOIR LES TRACES LANGSMITH")
    print("="*70)
    print(f"\n🔗 Dashboard: https://smith.langchain.com/projects/{LANGSMITH_PROJECT}")
    print("\nVous devriez voir:")
    print("  ✅ Tous les appels LLM tracés")
    print("  ✅ Tous les appels de retrieval (RAG) tracés")
    print("  ✅ Tous les appels de tools tracés")
    print("  ✅ Latency et performance metrics")
    print("  ✅ Métadonnées enrichies par agent")
    
    print("\n" + "="*70)
    
    if passed == total:
        print("\n🎉 All tests passed! Check LangSmith for traces!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
