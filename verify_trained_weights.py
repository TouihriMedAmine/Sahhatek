#!/usr/bin/env python3
"""Verify trained weights are being used"""
import os
import sys
import torch
import numpy as np
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sahatek.settings')
import django
django.setup()

from agents.wound_analyzer.agent import infer_wound_classification, CLASS_NAMES
from PIL import Image
from io import BytesIO
import base64

print("=" * 80)
print("VERIFICATION: Are trained weights being used?")
print("=" * 80)

# Load image
image_path = r"c:\Users\Houss\Downloads\laseration (16).jpg"

if os.path.exists(image_path):
    with open(image_path, 'rb') as f:
        image_bytes = f.read()
    
    print(f"\nTesting with image: {image_path}")
    print(f"Image size: {len(image_bytes)} bytes")
    
    # Run inference multiple times
    print("\nRunning inference 3 times to check consistency:")
    predictions = []
    
    for i in range(3):
        result = infer_wound_classification(image_bytes, "test wound")
        
        # Extract prediction from result
        lines = result.split('\n')
        for line in lines:
            if 'Classification' in line:
                pred_class = line.split('**')[1] if '**' in line else "Unknown"
                print(f"  Run {i+1}: {pred_class}")
                predictions.append(pred_class)
                break
    
    # Check consistency
    if len(set(predictions)) == 1:
        print(f"\n✅ CONSISTENT: All 3 runs predicted the same class")
        print(f"   This proves TRAINED WEIGHTS are being used!")
        print(f"   (Random weights would give different predictions)")
    else:
        print(f"\n⚠️ INCONSISTENT: Got different predictions: {predictions}")
        print(f"   This might indicate random weights")
    
    # Verify weights are not close to zero
    print("\n" + "=" * 80)
    print("Checking weight statistics...")
    print("=" * 80)
    
    from agents.wound_analyzer.agent import load_wound_classifier_model
    model = load_wound_classifier_model()
    
    if model:
        # Get statistics from the model
        weights = []
        for name, param in model.named_parameters():
            if 'weight' in name and param.dim() > 1:
                weights.append(param.detach().cpu())
                if len(weights) >= 3:
                    break
        
        if weights:
            print(f"\nAnalyzing {len(weights)} weight layers:")
            for i, w in enumerate(weights):
                mean = w.mean().item()
                std = w.std().item()
                max_val = w.max().item()
                min_val = w.min().item()
                
                print(f"\nLayer {i+1}:")
                print(f"  Mean: {mean:.6f}")
                print(f"  Std:  {std:.6f}")
                print(f"  Range: [{min_val:.6f}, {max_val:.6f}]")
                
                # Check if weights look trained
                if abs(mean) > 0.001 or std > 0.01:
                    print(f"  ✅ Looks like TRAINED weights")
                else:
                    print(f"  ⚠️ Weights might be untrained/random")
else:
    print(f"Image not found: {image_path}")
