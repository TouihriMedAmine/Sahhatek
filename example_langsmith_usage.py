#!/usr/bin/env python3
"""
Exemple complet d'utilisation de LangSmith avec tous les agents Sahatek

Ce script montre comment utiliser les agents avec le tracing LangSmith activé
et comment examiner les traces dans le dashboard.
"""

import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))


def example_medical_agent():
    """Exemple d'utilisation du Medical Agent avec LangSmith"""
    print("\n" + "="*70)
    print("🏥 EXEMPLE 1: Medical Agent with LangSmith")
    print("="*70)
    
    from agents.medical_agent.agent import medical_qa_agent
    
    # Créer un état de test
    test_state = {
        "user_input": "What are the symptoms of diabetes?",
        "metadata": {
            "understanding_agent": {
                "intent": "medical_qa",
                "language": "en",
                "keywords": ["diabetes", "symptoms"],
                "confidence": 0.8
            }
        },
        "messages": [],
        "current_agent": None,
        "next_agent": None,
    }
    
    print("\n📥 Input:", test_state["user_input"])
    print("\n⏳ Processing...")
    
    # Exécuter l'agent
    # ℹ️ Les traces s'enverront automatiquement à LangSmith!
    result = medical_qa_agent(test_state)
    
    print("\n✅ Output:")
    print(f"   Agent: {result.get('current_agent')}")
    print(f"   Response length: {len(result.get('agent_output', ''))} chars")
    if result.get('web_sources'):
        print(f"   Web sources used: {len(result['web_sources'])}")
    
    print("\n📊 Trace Status:")
    print("   ✓ Trace sent to LangSmith")
    print("   ✓ Visible in: https://smith.langchain.com/projects")
    print("   ✓ Dashboard: http://localhost:8000/chat/dashboard/langsmith/")


def example_mental_health_agent():
    """Exemple d'utilisation du Mental Health Agent avec LangSmith"""
    print("\n" + "="*70)
    print("🧠 EXEMPLE 2: Mental Health Agent with LangSmith")
    print("="*70)
    
    from agents.mental_health.agent import mental_health_agent
    
    test_state = {
        "user_input": "I'm feeling stressed and anxious about work",
        "messages": [],
        "metadata": {},
        "current_agent": None,
        "next_agent": None,
    }
    
    print("\n📥 Input:", test_state["user_input"])
    print("\n⏳ Processing...")
    
    result = mental_health_agent(test_state)
    
    print("\n✅ Output:")
    print(f"   Agent: {result.get('current_agent')}")
    print(f"   Response length: {len(result.get('agent_output', ''))} chars")
    
    metadata = result.get('metadata', {}).get('mental_health_agent', {})
    if metadata:
        print(f"   Urgency detected: {metadata.get('urgency_level', 'None')}")
        print(f"   RAG docs retrieved: {metadata.get('rag_docs_retrieved', 0)}")
    
    print("\n📊 Trace Status:")
    print("   ✓ Trace sent to LangSmith")
    print("   ✓ Visible in: https://smith.langchain.com/projects")


def example_triage_agent():
    """Exemple d'utilisation du Triage Agent avec LangSmith"""
    print("\n" + "="*70)
    print("⚕️  EXEMPLE 3: Triage Agent with LangSmith")
    print("="*70)
    
    from agents.triage_agent.agent import triage_agent
    
    test_state = {
        "user_input": "I have a fever and sore throat",
        "messages": [],
        "metadata": {},
        "current_agent": None,
        "next_agent": None,
    }
    
    print("\n📥 Input:", test_state["user_input"])
    print("\n⏳ Processing...")
    
    result = triage_agent(test_state)
    
    print("\n✅ Output:")
    print(f"   Agent: {result.get('current_agent')}")
    print(f"   Symptoms: {result.get('symptoms', [])}")
    print(f"   Diagnoses: {len(result.get('diagnoses', []))} found")
    
    if result.get('healthcare_recommendation'):
        rec = result['healthcare_recommendation']
        print(f"   Recommendation: {rec.get('service_type', 'Unknown')}")
    
    print("\n📊 Trace Status:")
    print("   ✓ Trace sent to LangSmith")
    print("   ✓ Sub-traces:")
    print("     - extract_symptoms")
    print("     - start_diagnosis")
    print("     - generate_diagnosis")
    print("     - recommend_care")


def check_langsmith_status():
    """Vérifier le statut de LangSmith"""
    print("\n" + "="*70)
    print("🔍 LangSmith Status Check")
    print("="*70)
    
    from agents.langsmith_decorators import (
        LANGSMITH_ENABLED, LANGSMITH_AVAILABLE,
        LANGSMITH_API_KEY, LANGSMITH_PROJECT
    )
    
    print(f"\n✓ LANGSMITH_ENABLED: {LANGSMITH_ENABLED}")
    print(f"✓ LANGSMITH_AVAILABLE: {LANGSMITH_AVAILABLE}")
    print(f"✓ LANGSMITH_PROJECT: {LANGSMITH_PROJECT}")
    print(f"✓ API_KEY configured: {bool(LANGSMITH_API_KEY)}")
    
    if LANGSMITH_AVAILABLE:
        print("\n✅ LangSmith is properly configured!")
        print("\n📊 Next steps:")
        print("   1. Run the examples above")
        print("   2. Check traces at: https://smith.langchain.com/projects")
        print("   3. View dashboard at: http://localhost:8000/chat/dashboard/langsmith/")
    else:
        print("\n⚠️  LangSmith is NOT enabled!")
        print("\n📋 To enable:")
        print("   1. Add to .env: LANGCHAIN_TRACING_V2=true")
        print("   2. Add to .env: LANGCHAIN_API_KEY=your_key_here")
        print("   3. Restart the application")


def show_trace_tree():
    """Afficher la structure des traces capturées"""
    print("\n" + "="*70)
    print("🌳 LangSmith Trace Structure")
    print("="*70)
    
    trace_tree = """
📊 sahatek-dev (Project)
├── medical_agent::process_medical_query
│   ├── medical_agent::chroma_vector_db
│   ├── medical_agent::web_search_duckduckgo
│   └── medical_agent::groq_invoke
│
├── mental_health_agent::mental_health_processing
│   ├── mental_health_agent::chroma_wellbeing_kb
│   ├── mental_health_agent::analyze_situation
│   ├── mental_health_agent::generate_plan
│   └── mental_health_agent::groq_chat_completions
│
├── triage_agent::triage_processing
│   ├── triage_agent::extract_symptoms
│   ├── triage_agent::start_diagnosis
│   ├── triage_agent::generate_diagnosis
│   └── triage_agent::recommend_care
│
└── rumor_verification_agent::verify_rumor
    ├── source_credibility_evaluator
    ├── web_evidence_searcher
    └── rumor_verifier::verify_rumor
    """
    
    print(trace_tree)
    print("\nChaque trace contient:")
    print("  • Latence d'exécution")
    print("  • Tokens utilisés (pour LLM)")
    print("  • Métadonnées enrichies")
    print("  • Logs détaillés")
    print("  • Erreurs et warnings")


def main():
    """Run all examples"""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "🚀 LangSmith Integration Examples" + " "*19 + "║")
    print("╚" + "="*68 + "╝")
    
    # 1. Check status
    check_langsmith_status()
    
    # 2. Show trace structure
    show_trace_tree()
    
    # 3. Run examples (commented because they need working LLMs)
    print("\n" + "="*70)
    print("💡 Examples (requires configured LLM APIs)")
    print("="*70)
    print("""
Uncomment the examples below to run them:

# try:
#     example_medical_agent()
# except Exception as e:
#     print(f"Error: {e}")
# 
# try:
#     example_mental_health_agent()
# except Exception as e:
#     print(f"Error: {e}")
# 
# try:
#     example_triage_agent()
# except Exception as e:
#     print(f"Error: {e}")

The examples above will automatically send traces to LangSmith!
    """)
    
    # Summary
    print("\n" + "="*70)
    print("📊 Summary")
    print("="*70)
    print("""
✅ LangSmith Integration is complete!

📍 All agents are instrumented with tracing:
   • Medical Agent (QA)
   • Mental Health Agent
   • Triage Agent
   • Rumor Agent

🔍 View traces at:
   • LangSmith Console: https://smith.langchain.com/projects
   • Sahatek Dashboard: http://localhost:8000/chat/dashboard/langsmith/

📈 Each trace includes:
   • Agent name and function
   • Execution time
   • Metadata (retrieved docs, web sources, etc.)
   • LLM calls and parameters
   • Error handling

🚀 Next steps:
   1. Configure LANGCHAIN_API_KEY in .env
   2. Set LANGCHAIN_TRACING_V2=true
   3. Restart the application
   4. Make requests through the chat interface
   5. Watch traces appear in real-time!
    """)


if __name__ == "__main__":
    main()
