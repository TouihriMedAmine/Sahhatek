#!/usr/bin/env python3
"""Test that the router correctly classifies new requests even with pending questions"""

import os
import sys
from pathlib import Path

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))

from agents.understanding_agent.agent import UnderstandingAgent

def test_router():
    """Test router with pending questions"""
    agent = UnderstandingAgent()
    
    test_cases = [
        ("i feel depressed", "mental_health", "Should route to mental health despite pending triage"),
        ("i have anxiety", "mental_health", "Should detect anxiety as mental health"),
        ("what is diabetes", "medical_qa", "Should detect medical QA"),
        ("yes", "triage", "Simple yes should be treated as triage answer"),
        ("no", "triage", "Simple no should be treated as triage answer"),
    ]
    
    print("\n" + "="*70)
    print("🧪 TESTING ROUTER WITH NEW REQUEST DETECTION")
    print("="*70)
    
    for query, expected_intent, description in test_cases:
        print(f"\n📝 Query: '{query}'")
        print(f"   Expected: {expected_intent}")
        print(f"   Reason: {description}")
        
        decision, msg = agent.process(query)
        
        status = "✅" if decision.intent.value == expected_intent else "❌"
        print(f"   {status} Got: {decision.intent.value}")
        print(f"   Route to: {decision.route_to}")
        print(f"   Response: {decision.response[:60]}..." if len(decision.response) > 60 else f"   Response: {decision.response}")

if __name__ == "__main__":
    test_router()
