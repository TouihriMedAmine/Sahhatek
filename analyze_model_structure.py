#!/usr/bin/env python3
"""Analyze the .pth file structure"""
import torch
import os

model_path = os.getenv('WOUND_MODEL_PATH', 'agents/wound_analyzer/wound_classifier_weights.pth')
state_dict = torch.load(model_path, map_location='cpu')

print("Analyzing model structure from state dict:")
print("=" * 80)

# Find FC/classifier layer
fc_keys = [k for k in state_dict.keys() if 'fc' in k or 'classifier' in k or '1.' in k]
print(f"\nFC/Classifier layers found: {fc_keys}")

# Check last few keys
print(f"\nLast 10 keys in state dict:")
for key in list(state_dict.keys())[-10:]:
    shape = state_dict[key].shape
    print(f"  {key}: {shape}")

# Find output dimension
last_key = list(state_dict.keys())[-1]
if 'weight' in last_key:
    output_dim = state_dict[last_key].shape[0]
    print(f"\nOutput dimension (from final weight layer): {output_dim}")

# Check if this is a full model or just body
print(f"\nTotal state dict size: {sum(p.numel() for p in state_dict.values())} parameters")
