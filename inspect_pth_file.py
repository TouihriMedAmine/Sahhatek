#!/usr/bin/env python3
"""Check what keys are in the .pth state dict"""
import torch
import os
from pathlib import Path

model_path = os.getenv('WOUND_MODEL_PATH', 'agents/wound_analyzer/wound_classifier_weights.pth')

print(f"Loading: {model_path}")
print(f"Exists: {os.path.exists(model_path)}")

# Load the state dict
state_dict = torch.load(model_path, map_location='cpu')

print(f"\nState Dict Keys ({len(state_dict)} keys):")
for i, key in enumerate(list(state_dict.keys())[:20]):
    print(f"  {i+1}. {key}")
    print(f"     Shape: {state_dict[key].shape}")
    print(f"     Mean: {state_dict[key].mean():.6f}")
    print(f"     Std: {state_dict[key].std():.6f}")
    if i >= 4:
        print(f"  ... and {len(state_dict) - 5} more keys")
        break

# Check if this is a FastAI learner state dict (which has a different format)
print(f"\nState Dict Summary:")
print(f"  Total keys: {len(state_dict)}")
print(f"  First key: {list(state_dict.keys())[0]}")
print(f"  Last key: {list(state_dict.keys())[-1]}")

# Check if it looks like FastAI format (starts with 0. or 1.)
sample_keys = list(state_dict.keys())[:5]
if any(key.startswith('0.') or key.startswith('1.') for key in sample_keys):
    print(f"\n⚠️ WARNING: This looks like FastAI Sequential format, not standard PyTorch!")
    print(f"Sample keys: {sample_keys}")
else:
    print(f"\n✓ Standard PyTorch format detected")
    print(f"Sample keys: {sample_keys}")
