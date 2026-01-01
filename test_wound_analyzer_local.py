#!/usr/bin/env python3
"""
Local test script for the Wound Analyzer Agent
Tests the agent directly without browser/HTTP
"""

import os
import sys
import base64
import json
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sahatek.settings')

import django
django.setup()

from agents.wound_analyzer.agent import wound_analyzer_agent

def load_image_as_base64(image_path: str) -> str:
    """Load image file and convert to base64"""
    with open(image_path, 'rb') as f:
        image_data = f.read()
    return f"data:image/jpeg;base64,{base64.b64encode(image_data).decode()}"

def test_wound_analyzer():
    """Test the wound analyzer agent with a real image"""
    
    # Image path from user
    image_path = r"C:\Users\Rahma\Downloads\1.jpg"
    
    if not os.path.exists(image_path):
        print(f"[ERROR] Image not found: {image_path}")
        return
    
    print(f"[OK] Found image: {image_path}")
    print(f"     Size: {os.path.getsize(image_path)} bytes")
    
    # Convert to base64
    print("\n[PROCESSING] Converting image to base64...")
    image_base64 = load_image_as_base64(image_path)
    print(f"[OK] Base64 length: {len(image_base64)} characters")
    
    # Create test state
    print("\n[SETUP] Creating test state...")
    test_state = {
        "user_input": "Analyze this wound image for classification and severity",
        "messages": [],
        "metadata": {
            "image": image_base64
        },
        "current_agent": None,
        "next_agent": None,
        "agent_output": None,
    }
    
    print(f"     User input: {test_state['user_input']}")
    print(f"     Image attached: {bool(test_state['metadata'].get('image'))}")
    
    # Call wound analyzer directly
    print("\n[RUN] Invoking Wound Analyzer Agent...")
    print("=" * 80)
    
    try:
        result = wound_analyzer_agent(test_state)
        
        print("=" * 80)
        print("\n[SUCCESS] WOUND ANALYZER RESPONSE:")
        print("-" * 80)
        
        if result.get("agent_output"):
            print(result["agent_output"])
        else:
            print("(No output returned)")
        
        print("\n[METADATA]:")
        print(f"     Current Agent: {result.get('current_agent')}")
        print(f"     Next Agent: {result.get('next_agent')}")
        
        if result.get("metadata"):
            print(f"\n[ANALYSIS DATA]:")
            for key, value in result["metadata"].items():
                if key != "image":  # Don't print the full base64 image
                    print(f"     {key}: {value}")
        
        print("\n[COMPLETE] Test completed successfully")
        
    except Exception as e:
        print("=" * 80)
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("[WOUND ANALYZER LOCAL TEST]")
    print("=" * 80)
    test_wound_analyzer()