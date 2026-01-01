#!/usr/bin/env python3
"""Check if model file is being found and loaded"""
import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env
from dotenv import load_dotenv
load_dotenv()

print("=" * 80)
print("MODEL LOADING VERIFICATION")
print("=" * 80)

# Check environment variable
wound_model_path = os.getenv('WOUND_MODEL_PATH')
print(f"\n1. WOUND_MODEL_PATH environment variable:")
print(f"   Value: {wound_model_path}")
print(f"   Exists: {os.path.exists(wound_model_path) if wound_model_path else 'Variable not set'}")

# Check default
default_path = 'wound_classifier_weights.pth'
print(f"\n2. Default path: {default_path}")
print(f"   Exists: {os.path.exists(default_path)}")

# Check in agents/wound_analyzer
wa_path = 'agents/wound_analyzer/wound_classifier_weights.pth'
print(f"\n3. In agents/wound_analyzer: {wa_path}")
print(f"   Exists: {os.path.exists(wa_path)}")

# Find all .pth files
import glob
pth_files = glob.glob('**/*.pth', recursive=True)
print(f"\n4. All .pth files found:")
if pth_files:
    for f in pth_files:
        print(f"   - {f}")
        print(f"     Size: {os.path.getsize(f) / (1024*1024):.1f} MB")
else:
    print("   (None found)")

# Now test loading
print("\n" + "=" * 80)
print("TESTING MODEL LOAD")
print("=" * 80)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sahatek.settings')
django.setup()

from agents.wound_analyzer.agent import load_wound_classifier_model

model = load_wound_classifier_model()
print(f"\nModel loaded: {model is not None}")
if model:
    print(f"Model type: {type(model)}")
    print(f"Model eval mode: {model.training == False}")
else:
    print("Model is None - WEIGHTS NOT LOADED!")
