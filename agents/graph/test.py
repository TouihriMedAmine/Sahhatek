# agents/graph/test.py
import sys
import os
import time

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from agents.graph.build_graph import app
    from agents.graph.registry import AGENT_REGISTRY
    from agents.understanding_agent.agent import get_gatekeeper_agent
    
    print("✅ Imports successful!")
    print("🚀 Testing Medical Gatekeeper Agent System")
    print("=" * 70)
    
    # First, test gatekeeper directly for debugging
    print("\n🔍 INITIAL GATEKEEPER DEBUGGING")
    print("-" * 70)
    
    gatekeeper = get_gatekeeper_agent()
    
    debug_queries = [
        ("What is an asthma attack?", "medical_qa"),
        ("I have severe chest pain!", "triage"),
        ("I feel very depressed and anxious", "mental_health"),
        ("My friend said vaccines cause autism", "rumor"),
        ("عندي وجع ف الصدر", "triage"),
    ]
    
    for query, expected in debug_queries:
        print(f"\n🔬 Debugging: '{query}'")
        debug_info = gatekeeper.debug_decision(query)
        
        if debug_info.get("route_to") == expected:
            print(f"✅ DEBUG CORRECT: Expected {expected}, got {debug_info.get('route_to')}")
        else:
            print(f"❌ DEBUG MISMATCH: Expected {expected}, got {debug_info.get('route_to')}")
        
        time.sleep(1)
    
    # Enhanced test queries covering all scenarios
    test_queries = [
        # Medical queries within scope
        ("What is an asthma attack?", "medical_qa", "Medical query within scope"),
        ("I have severe chest pain!", "triage", "Emergency symptom"),
        ("High fever and cough for 3 days", "medical_qa", "Urgent medical"),
        ("Signs of a stroke to watch for", "medical_qa", "Medical education (borderline)"),
        
        # Specialized agent queries
        ("I feel very depressed and anxious", "mental_health", "Mental health concern"),
        ("My friend said vaccines cause autism", "rumor", "Rumor verification"),
        
        # Non-medical queries (should be handled by gatekeeper)
        ("Hello, how are you?", "gatekeeper", "Greeting - non-medical"),
        ("What's the weather like today?", "gatekeeper", "Weather - non-medical"),
        ("Tell me a joke", "gatekeeper", "Entertainment - non-medical"),
        
        # Vague medical queries (should ask for clarification)
        ("I don't feel good", "gatekeeper", "Vague symptom"),
        ("I'm sick", "gatekeeper", "Too vague"),
        ("Help me", "gatekeeper", "Too short/vague"),
        
        # Out-of-scope medical (chronic management, dosage, etc.)
        ("How to manage diabetes long-term?", "gatekeeper", "Chronic management - out of scope"),
        ("What's the dosage for ibuprofen?", "gatekeeper", "Medication dosage - out of scope"),
        ("Explain human anatomy", "gatekeeper", "Medical education - out of scope"),
        
        # Tunisian Arabic test (if supported)
        ("عندي وجع ف الصدر", "triage", "Tunisian Arabic - chest pain"),
        ("ما نحسش ب خير", "gatekeeper", "Tunisian Arabic - vague"),
    ]
    
    passed_tests = 0
    total_tests = len(test_queries)
    
    for query, expected_agent, description in test_queries:
        print(f"\n{'='*70}")
        print(f"🧪 Test: {description}")
        print(f"📥 Query: '{query}'")
        print('-'*70)
        
        # Create test state
        test_state = {
            "user_input": query,
            "intent": None,
            "messages": [],
            "current_agent": None,
            "next_agent": None,
            "agent_output": None,
            "agent_registry": AGENT_REGISTRY,
            "metadata": {},
            "should_end": False
        }
        
        try:
            # Run through LangGraph
            result = app.invoke(test_state)
            
            # Get the final state
            final_agent = result.get("current_agent", "unknown")
            intent = result.get("intent", "none")
            agent_output = result.get("agent_output", "")
            should_end = result.get("should_end", False)
            gatekeeper_decision = result.get("gatekeeper_decision", {})
            
            # Print results
            print(f"🎯 Intent: {intent}")
            print(f"🤖 Final Agent: {final_agent}")
            print(f"🔄 Should End: {should_end}")
            
            # Check for gatekeeper metadata
            if result.get("metadata", {}).get("gatekeeper_agent"):
                gatekeeper_info = result["metadata"]["gatekeeper_agent"]
                print(f"🌍 Language: {gatekeeper_info.get('normalized_language', 'unknown')}")
                if gatekeeper_info.get('translation_used'):
                    print(f"🔤 Translation used: Yes")
            
            # Display gatekeeper decision details if available
            if gatekeeper_decision:
                print(f"⚖️ Gatekeeper Decision:")
                if "emergency_level" in gatekeeper_decision:
                    print(f"   - Emergency Level: {gatekeeper_decision.get('emergency_level')}")
                if "analysis" in gatekeeper_decision and "reason" in gatekeeper_decision["analysis"]:
                    print(f"   - Reason: {gatekeeper_decision['analysis']['reason'][:100]}...")
            
            # Output preview
            output_preview = agent_output[:150] + "..." if len(agent_output) > 150 else agent_output
            print(f"📝 Output ({len(agent_output)} chars):")
            print(f"   {output_preview}")
            
            # Check escalation
            if result.get('next_agent') and not should_end:
                print(f"⚠️ Would escalate to: {result['next_agent']}")
            
            # Test validation
            test_passed = False
            if expected_agent == "gatekeeper":
                # Should be handled by gatekeeper (router agent)
                if final_agent == "router" or should_end:
                    print(f"✅ TEST PASSED: Gatekeeper correctly handled non-medical/vague query")
                    test_passed = True
                else:
                    print(f"❌ TEST FAILED: Expected gatekeeper handling, but routed to {final_agent}")
            else:
                # Should be routed to specific agent
                actual_agent = result.get("next_agent") or final_agent
                if actual_agent == expected_agent:
                    print(f"✅ TEST PASSED: Correctly routed to {expected_agent}")
                    test_passed = True
                else:
                    print(f"❌ TEST FAILED: Expected {expected_agent}, got {actual_agent}")
            
            if test_passed:
                passed_tests += 1
                
        except Exception as e:
            print(f"❌ TEST ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n{'='*70}")
    print("📊 TEST SUMMARY")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {total_tests - passed_tests}")
    print(f"   Success Rate: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Gatekeeper is working correctly.")
    else:
        print("⚠️ Some tests failed. Review the gatekeeper logic.")
    
    # Additional diagnostic tests
    print(f"\n{'='*70}")
    print("🔍 DIAGNOSTIC TESTS")
    print('='*70)
    
    # Test emergency detection
    emergency_queries = [
        ("I can't breathe!", "Should route to triage with critical emergency"),
        ("Severe chest pain radiating to left arm", "Should be critical emergency"),
        ("Mild headache", "Should be non-urgent medical"),
        ("What's for dinner?", "Should be non-medical"),
    ]
    
    for eq, desc in emergency_queries:
        print(f"\n🔬 Testing: '{eq}'")
        test_state = {
            "user_input": eq,
            "intent": None,
            "messages": [],
            "current_agent": None,
            "next_agent": None,
            "agent_output": None,
            "agent_registry": AGENT_REGISTRY,
            "metadata": {}
        }
        
        try:
            result = app.invoke(test_state)
            gatekeeper_info = result.get("metadata", {}).get("gatekeeper_agent", {})
            decision = result.get("gatekeeper_decision", {})
            
            print(f"   Description: {desc}")
            print(f"   Final Agent: {result.get('current_agent')}")
            print(f"   Emergency Level: {decision.get('emergency_level', 'unknown')}")
            print(f"   Should Route: {not result.get('should_end', True)}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "="*70)
    print("✅ Testing completed!")
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("⚠️ Make sure:")
    print("   1. You're running from the project root directory")
    print("   2. All agent files are in the correct locations")
    print("   3. You've updated build_graph.py with the new gatekeeper routing")
    
    # Try to diagnose import issues
    print("\n🔍 Checking imports...")
    try:
        import importlib
        # Try to import each component separately
        modules_to_check = [
            "agents.graph.build_graph",
            "agents.understanding_agent.agent",
            "agents.medical_agent.agent",
            "langgraph.graph"
        ]
        
        for module in modules_to_check:
            try:
                importlib.import_module(module)
                print(f"   ✅ {module} imports successfully")
            except ImportError as e:
                print(f"   ❌ {module}: {e}")
                
    except Exception as e:
        print(f"   ❌ Diagnostic failed: {e}")
        
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
    import traceback
    traceback.print_exc()
    
    print("\n💡 Troubleshooting tips:")
    print("   1. Check that your updated build_graph.py has the new gatekeeper_routing_decision function")
    print("   2. Ensure router_agent sets 'should_end' = True for non-medical queries")
    print("   3. Verify the understanding_agent.agent.py has the new gatekeeper logic")
    print("   4. Make sure all imports are correct in your agent files")