# agents/triage_agent/demo_knowledge_base.py
"""
Demo script showing the Knowledge Base integration with triage system
Tests Q&A, recommendations, and emergency detection
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.triage_agent.knowledge_base import get_knowledge_base
from agents.triage_agent.agent import triage_agent

# ============================================================
# DEMO: Knowledge Base Usage
# ============================================================

def demo_knowledge_base():
    """Demo knowledge base functionality"""
    print("\n" + "="*70)
    print("🧠 TRIAGE KNOWLEDGE BASE DEMO")
    print("="*70 + "\n")
    
    kb = get_knowledge_base()
    
    # 1. Test retrieval
    print("1️⃣ Testing Knowledge Base Retrieval:")
    print("-" * 70)
    results = kb.retrieve("fever", k=2)
    for i, result in enumerate(results, 1):
        print(f"\nResult {i}: {result.source}")
        print(f"Score: {result.score:.3f}")
        print(f"Category: {result.metadata.get('category')}")
        print(f"Content (first 200 chars): {result.content[:200]}...")
    
    # 2. Test category retrieval
    print("\n\n2️⃣ Testing Category Retrieval (recommendations):")
    print("-" * 70)
    results = kb.retrieve_by_category("recommendations", limit=3)
    for result in results:
        print(f"- {result.source}: {result.metadata.get('service_type', 'N/A')}")
    
    # 3. Test Q&A
    print("\n\n3️⃣ Testing Q&A Functionality:")
    print("-" * 70)
    questions = [
        "When should I go to the hospital?",
        "What's the difference between a cold and the flu?",
        "When do I need antibiotics?",
        "How do I know if I have a fever?"
    ]
    
    for q in questions:
        print(f"\nQ: {q}")
        answer = kb.answer_question(q)
        print(f"A: {answer[:300]}...")
    
    # 4. Test emergency detection
    print("\n\n4️⃣ Testing Emergency Detection:")
    print("-" * 70)
    emergency_phrases = [
        "I have chest pain",
        "I'm having trouble breathing",
        "I'm suicidal",
        "I just fell and broke my arm",
        "I can't stop bleeding"
    ]
    
    for phrase in emergency_phrases:
        is_emergency, guidance = kb.is_emergency(phrase)
        status = "🚨 EMERGENCY" if is_emergency else "✅ Not Emergency"
        print(f"\n{status}: {phrase}")
        if is_emergency:
            print(f"Guidance (first 150 chars): {guidance[:150]}...")
    
    # 5. Test recommendation context
    print("\n\n5️⃣ Testing Recommendation Context Generation:")
    print("-" * 70)
    diagnoses = [
        {"name": "Influenza", "confidence": 0.87},
        {"name": "Common Cold", "confidence": 0.45}
    ]
    symptoms = ["fever", "cough", "headache"]
    context = kb.get_recommendation_context(diagnoses, symptoms)
    print(f"Context generated ({len(context)} chars):")
    print(context[:500])
    print("...")
    
    # 6. Test care paths
    print("\n\n6️⃣ Testing Care Paths:")
    print("-" * 70)
    respiratory_path = kb.get_care_path(["cough", "sore throat"])
    print("Respiratory symptoms care path:")
    print(respiratory_path[:400] if respiratory_path else "Not found")
    print("...")
    
    fever_path = kb.get_care_path(["fever", "chills"])
    print("\nFever symptoms care path:")
    print(fever_path[:400] if fever_path else "Not found")
    print("...")

# ============================================================
# DEMO: Triage Agent with KB
# ============================================================

def demo_triage_with_kb():
    """Demo triage agent using knowledge base"""
    print("\n" + "="*70)
    print("🏥 TRIAGE AGENT WITH KNOWLEDGE BASE DEMO")
    print("="*70 + "\n")
    
    # Test case 1: Flu symptoms
    print("Test Case 1: Flu Symptoms")
    print("-" * 70)
    state1 = {
        "user_input": "I have fever 39°C, body aches, and a dry cough",
        "intent": None,
        "metadata": {"age": "32", "location": "36.8065,10.1686"},
        "messages": [],
        "current_agent": None,
        "next_agent": None,
        "agent_output": None
    }
    
    result1 = triage_agent(state1)
    print(f"Symptoms: {result1.get('symptoms')}")
    print(f"Diagnoses: {[d.get('name') for d in result1.get('diagnoses', [])]}")
    rec = result1.get('healthcare_recommendation', {})
    print(f"Recommendation: {rec.get('service_type')} (immediate: {rec.get('immediate_care')})")
    print(f"Agent output: {result1.get('agent_output')}")
    
    # Test case 2: Emergency
    print("\n\nTest Case 2: Emergency Situation")
    print("-" * 70)
    state2 = {
        "user_input": "I have severe chest pain and difficulty breathing",
        "intent": None,
        "metadata": {"age": "55"},
        "messages": [],
        "current_agent": None,
        "next_agent": None,
        "agent_output": None
    }
    
    result2 = triage_agent(state2)
    rec = result2.get('healthcare_recommendation', {})
    print(f"Emergency: {rec.get('emergency', False)}")
    print(f"Recommendation: {rec.get('service_type')} (immediate: {rec.get('immediate_care')})")
    print(f"Agent output: {result2.get('agent_output')}")
    print(f"Guidance (first 200 chars): {rec.get('guidance', '')[:200]}...")
    
    # Test case 3: Q&A
    print("\n\nTest Case 3: Q&A Question")
    print("-" * 70)
    state3 = {
        "user_input": "When should I go to the hospital instead of seeing my regular doctor?",
        "intent": None,
        "metadata": {},
        "messages": [],
        "current_agent": None,
        "next_agent": None,
        "agent_output": None
    }
    
    result3 = triage_agent(state3)
    print(f"Response: {result3.get('qa_response', 'N/A')[:400]}...")
    print(f"Agent output: {result3.get('agent_output')}")

# ============================================================
# DEMO: Integration Verification
# ============================================================

def verify_integration():
    """Verify knowledge base integration"""
    print("\n" + "="*70)
    print("✅ INTEGRATION VERIFICATION")
    print("="*70 + "\n")
    
    try:
        kb = get_knowledge_base()
        print(f"✅ Knowledge base initialized")
        
        # Check vectorstore
        if kb.vectorstore:
            count = kb.vectorstore._collection.count()
            print(f"✅ Vectorstore loaded with {count} documents")
        else:
            print(f"❌ Vectorstore not initialized")
            return
        
        # Test retrieval
        results = kb.retrieve("fever")
        print(f"✅ Retrieval working ({len(results)} results)")
        
        # Test Q&A
        answer = kb.answer_question("What is fever?")
        if len(answer) > 0:
            print(f"✅ Q&A working ({len(answer)} chars)")
        
        # Test emergency detection
        is_emergency, _ = kb.is_emergency("chest pain")
        if is_emergency:
            print(f"✅ Emergency detection working")
        
        # Test triage agent
        from agents.triage_agent import triage_agent
        state = {
            "user_input": "I have fever",
            "intent": None,
            "metadata": {},
            "messages": [],
            "current_agent": None,
            "next_agent": None,
            "agent_output": None
        }
        result = triage_agent(state)
        if result.get("agent_output"):
            print(f"✅ Triage agent working")
        
        print("\n🎉 All integrations verified successfully!")
        
    except Exception as e:
        print(f"❌ Integration error: {e}")
        import traceback
        traceback.print_exc()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("\n🚀 Starting Knowledge Base Demos...\n")
    
    # Run demos
    try:
        verify_integration()
        demo_knowledge_base()
        demo_triage_with_kb()
        
        print("\n" + "="*70)
        print("✅ All demos completed successfully!")
        print("="*70 + "\n")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
