# Triage Agent Data Directory

This directory contains the data files required for the triage agent to function independently.

## Required Files

- **nhs_conditions2.json** - Medical conditions database (required for diagnosis)

## Optional Files (for better performance)

- **full_medical_index.faiss** - FAISS vector index for full medical knowledge base
- **full_medical_metadata.pkl** - Metadata for full FAISS index
- **fast_medical_index.faiss** - FAISS vector index for fast/common conditions
- **fast_medical_metadata.pkl** - Metadata for fast FAISS index

## Fallback Behavior

If FAISS files are not available, the agent will fall back to JSON-based search using `nhs_conditions2.json`.

If no data files are available, the agent will still function but with limited knowledge base access.


