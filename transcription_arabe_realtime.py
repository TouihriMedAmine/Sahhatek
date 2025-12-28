# -*- coding: utf-8 -*-
"""
Standalone Real-time Arabic Transcription Script
Based on the original transcription_arabe_realtime.py
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.speech.transcription import create_gradio_interface

if __name__ == "__main__":
    print("🎙️ Starting Real-time Arabic Transcription...")
    
    # Try to find model path
    model_path = None
    possible_paths = [
        "Modele_huhugging/vosk-model/vosk-model",
        "maaaheeeerrr/Modele_huhugging/vosk-model/vosk-model",
        os.path.join(os.path.dirname(__file__), "maaaheeeerrr", "Modele_huhugging", "vosk-model", "vosk-model"),
    ]
    
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            model_path = abs_path
            print(f"✅ Using model at: {model_path}")
            break
    
    if not model_path:
        print("⚠️ Model not found. Please specify MODEL_PATH environment variable or update the script.")
        print("   Looking for: vosk-model/vosk-model directory")
    
    # Create and launch interface
    try:
        interface_func = create_gradio_interface(model_path)
        demo = interface_func()
        print("\n🚀 Launching Gradio interface...")
        demo.launch()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

