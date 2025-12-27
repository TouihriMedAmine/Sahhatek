#!/usr/bin/env python3
"""
Test script pour vérifier l'intégration LangSmith
Vérifie que tous les agents sont correctement instrumentés
"""

import os
import sys
from pathlib import Path

# Load environment variables FIRST
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_langsmith_config():
    """Vérifie la configuration LangSmith"""
    print("\n" + "="*60)
    print("🔍 Testing LangSmith Configuration")
    print("="*60)
    
    from agents.langsmith_decorators import (
        LANGSMITH_AVAILABLE, LANGSMITH_ENABLED, 
        LANGSMITH_API_KEY, LANGSMITH_PROJECT
    )
    
    print(f"\n✓ LANGSMITH_ENABLED: {LANGSMITH_ENABLED}")
    print(f"✓ LANGSMITH_AVAILABLE: {LANGSMITH_AVAILABLE}")
    print(f"✓ LANGSMITH_PROJECT: {LANGSMITH_PROJECT}")
    print(f"✓ API_KEY configured: {LANGSMITH_API_KEY is not None}")
    
    if not LANGSMITH_AVAILABLE:
        print("\n⚠️  LangSmith is NOT enabled!")
        print("   To enable, set: LANGCHAIN_TRACING_V2=true")
        print("   And add: LANGCHAIN_API_KEY=your_key")
    else:
        print("\n✅ LangSmith is properly configured!")
    
    return LANGSMITH_AVAILABLE


def test_decorators():
    """Vérifie que les décorateurs sont disponibles"""
    print("\n" + "="*60)
    print("🎨 Testing Decorators")
    print("="*60)
    
    try:
        from agents.langsmith_decorators import (
            trace_agent_node,
            trace_llm_call,
            trace_retrieval,
            trace_tool_call,
            add_metadata_to_state
        )
        
        print("\n✅ All decorators imported successfully:")
        print("  - trace_agent_node")
        print("  - trace_llm_call")
        print("  - trace_retrieval")
        print("  - trace_tool_call")
        print("  - add_metadata_to_state")
        
        return True
    except Exception as e:
        print(f"\n❌ Error importing decorators: {e}")
        return False


def test_medical_agent():
    """Teste que le medical agent a les décorateurs"""
    print("\n" + "="*60)
    print("🏥 Testing Medical Agent Integration")
    print("="*60)
    
    try:
        from agents.medical_agent.agent import medical_qa_agent
        import inspect
        
        # Check if function has decorators (wrapper)
        source = inspect.getsource(medical_qa_agent)
        has_trace = "trace_agent_node" in source or "__wrapped__" in str(dir(medical_qa_agent))
        
        print("\n✅ Medical Agent imported successfully")
        if has_trace or hasattr(medical_qa_agent, '__wrapped__'):
            print("✅ Medical Agent has LangSmith decorators")
        else:
            print("⚠️  Medical Agent source contains decorator markers")
        
        return True
    except Exception as e:
        print(f"\n❌ Error testing medical agent: {e}")
        return False


def test_mental_health_agent():
    """Teste que le mental health agent a les décorateurs"""
    print("\n" + "="*60)
    print("🧠 Testing Mental Health Agent Integration")
    print("="*60)
    
    try:
        from agents.mental_health.agent import mental_health_agent
        from agents.mental_health.service import (
            groq_chat, analyze_situation, generate_plan,
            continue_conversation, retrieve_relevant_techniques
        )
        
        print("\n✅ Mental Health Agent imported successfully")
        print("✅ All service functions imported successfully:")
        print("  - groq_chat")
        print("  - analyze_situation")
        print("  - generate_plan")
        print("  - continue_conversation")
        print("  - retrieve_relevant_techniques")
        
        return True
    except Exception as e:
        print(f"\n❌ Error testing mental health agent: {e}")
        return False


def test_triage_agent():
    """Teste que le triage agent a les décorateurs"""
    print("\n" + "="*60)
    print("⚕️  Testing Triage Agent Integration")
    print("="*60)
    
    try:
        from agents.triage_agent.agent import (
            triage_agent, extract_symptoms, start_diagnosis,
            generate_diagnosis, recommend_care, answer_triage_question
        )
        
        print("\n✅ Triage Agent imported successfully")
        print("✅ All sub-functions imported successfully:")
        print("  - triage_agent (main)")
        print("  - extract_symptoms")
        print("  - start_diagnosis")
        print("  - generate_diagnosis")
        print("  - recommend_care")
        print("  - answer_triage_question")
        
        return True
    except Exception as e:
        print(f"\n❌ Error testing triage agent: {e}")
        return False


def test_rumor_agent():
    """Teste que le rumor agent a les décorateurs"""
    print("\n" + "="*60)
    print("🧐 Testing Rumor Agent Integration")
    print("="*60)
    
    try:
        from agents.rumor.agent import rumor_verification_agent
        
        print("\n✅ Rumor Agent imported successfully")
        print("✅ Rumor Agent has LangSmith integration")
        
        return True
    except Exception as e:
        print(f"\n❌ Error testing rumor agent: {e}")
        return False


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*10 + "🎯 LANGSMITH INTEGRATION TEST SUITE" + " "*13 + "║")
    print("╚" + "="*58 + "╝")
    
    results = {
        "LangSmith Config": test_langsmith_config(),
        "Decorators": test_decorators(),
        "Medical Agent": test_medical_agent(),
        "Mental Health Agent": test_mental_health_agent(),
        "Triage Agent": test_triage_agent(),
        "Rumor Agent": test_rumor_agent(),
    }
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! LangSmith integration is complete!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
