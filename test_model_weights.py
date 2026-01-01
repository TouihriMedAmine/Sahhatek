#!/usr/bin/env python3
"""Test if model weights are actually being used for predictions"""
import os
import sys
import torch
import numpy as np
from pathlib import Path
from PIL import Image
from io import BytesIO
import base64

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sahatek.settings')
import django
django.setup()

from agents.wound_analyzer.agent import load_wound_classifier_model, CLASS_NAMES

print("=" * 80)
print("TEST 1: Check if weights are loaded (not random)")
print("=" * 80)

# Load model
model = load_wound_classifier_model()
print(f"\nModel loaded: {model is not None}")

if model:
    # Get first layer weights
    first_conv_weight = model.conv1.weight
    print(f"\nFirst Conv Layer Stats:")
    print(f"  Shape: {first_conv_weight.shape}")
    print(f"  Mean: {first_conv_weight.mean():.6f}")
    print(f"  Std: {first_conv_weight.std():.6f}")
    print(f"  Min: {first_conv_weight.min():.6f}")
    print(f"  Max: {first_conv_weight.max():.6f}")
    
    # Random weights would have very different statistics
    # Trained weights should have specific patterns
    
    # Get output layer
    output_weight = model.fc.weight
    print(f"\nOutput FC Layer Stats (10 classes):")
    print(f"  Shape: {output_weight.shape}")
    print(f"  Mean: {output_weight.mean():.6f}")
    print(f"  Std: {output_weight.std():.6f}")

print("\n" + "=" * 80)
print("TEST 2: Test inference on different image")
print("=" * 80)

# Load image
image_path = r"c:\Users\Houss\Downloads\laseration (16).jpg"
if os.path.exists(image_path):
    # Load and preprocess
    img = Image.open(image_path).convert('RGB')
    
    from torchvision import transforms
    preprocess = transforms.Compose([
        transforms.Resize(224),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225]),
    ])
    
    input_tensor = preprocess(img)
    input_batch = input_tensor.unsqueeze(0)
    
    # Run inference
    with torch.no_grad():
        output = model(input_batch)
        probs = torch.nn.functional.softmax(output, dim=1)
    
    # Get predictions
    confidence_scores = probs[0].cpu().numpy()
    pred_class_idx = np.argmax(confidence_scores)
    confidence = float(confidence_scores[pred_class_idx])
    
    print(f"\nPrediction Results:")
    print(f"  Predicted class: {CLASS_NAMES[pred_class_idx]}")
    print(f"  Confidence: {confidence:.4f} ({confidence*100:.1f}%)")
    
    print(f"\nAll class probabilities:")
    for i, (class_name, prob) in enumerate(zip(CLASS_NAMES, confidence_scores)):
        print(f"  {i:2d}. {class_name:20s} {prob:.4f} ({prob*100:5.1f}%)")
    
    print(f"\nTop 3 predictions:")
    top_3_idx = np.argsort(confidence_scores)[-3:][::-1]
    for rank, idx in enumerate(top_3_idx, 1):
        print(f"  {rank}. {CLASS_NAMES[idx]:20s} {confidence_scores[idx]:.4f}")
else:
    print(f"Image not found: {image_path}")

print("\n" + "=" * 80)
print("TEST 3: Verify different inputs give different outputs")
print("=" * 80)

# Test with noise
print("\nTesting with random noise input:")
random_input = torch.randn(1, 3, 224, 224)
with torch.no_grad():
    random_output = model(random_input)
    random_probs = torch.nn.functional.softmax(random_output, dim=1)
    random_scores = random_probs[0].cpu().numpy()

print(f"  Top class: {CLASS_NAMES[np.argmax(random_scores)]}")
print(f"  Confidence: {np.max(random_scores):.4f}")

# Compare with actual image
print(f"\nComparing outputs:")
print(f"  Real image max prob: {np.max(confidence_scores):.4f}")
print(f"  Random noise max prob: {np.max(random_scores):.4f}")
print(f"  Different predictions: {np.argmax(confidence_scores) != np.argmax(random_scores)}")
