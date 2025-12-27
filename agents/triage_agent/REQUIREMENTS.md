# Triage Agent - Required Files and Folders

## 📁 Directory Structure

```
agents/triage_agent/
├── __init__.py                    # ✅ REQUIRED - Module initialization
├── agent.py                       # ✅ REQUIRED - Main agent implementation
├── nodes.py                       # ✅ REQUIRED - LangGraph nodes (extraction, diagnosis, triage, orientation)
├── diagnosis_utils.py            # ✅ REQUIRED - Independent diagnosis utilities
├── diagnosis_logic.py             # ✅ REQUIRED - Diagnosis helper functions
├── knowledge_base.py              # ✅ REQUIRED - Knowledge base for healthcare recommendations
├── workflow.py                    # ✅ REQUIRED - Workflow definition
│
├── data/                          # ✅ REQUIRED - Data directory
│   ├── nhs_conditions2.json      # ✅ REQUIRED - Medical conditions database
│   ├── full_medical_index.faiss   # ⚠️ OPTIONAL - FAISS index (for better performance)
│   ├── full_medical_metadata.pkl  # ⚠️ OPTIONAL - FAISS metadata (for better performance)
│   ├── fast_medical_index.faiss   # ⚠️ OPTIONAL - Fast FAISS index
│   ├── fast_medical_metadata.pkl  # ⚠️ OPTIONAL - Fast FAISS metadata
│   └── README.md                  # Documentation
│
└── [Documentation files]          # ⚠️ OPTIONAL - Documentation only
    ├── README.md
    ├── ARCHITECTURE.md
    ├── DIAGNOSIS_GUIDE.md
    ├── QUICK_REFERENCE.md
    ├── QUICKSTART.md
    ├── README_NODES.md
    ├── INDEPENDENCE.md
    └── REQUIREMENTS.md (this file)
```

## ✅ Required Files (Core Functionality)

### 1. **Core Python Files** (All Required)

| File | Purpose | Can Delete? |
|------|---------|-------------|
| `__init__.py` | Module initialization, exports | ❌ NO |
| `agent.py` | Main agent logic, healthcare recommendations | ❌ NO |
| `nodes.py` | LangGraph nodes (extraction, diagnosis, triage, orientation) | ❌ NO |
| `diagnosis_utils.py` | Independent diagnosis functions (normalize_symptom, determine_age_group, retrieve_conditions_faiss, generate_diagnosis_llm) | ❌ NO |
| `diagnosis_logic.py` | Diagnosis helper functions (confidence calculation, question generation) | ❌ NO |
| `knowledge_base.py` | Knowledge base for healthcare recommendations | ❌ NO |
| `workflow.py` | Workflow definition for LangGraph | ❌ NO |

### 2. **Data Files** (Required for Diagnosis)

| File | Purpose | Required? | Fallback |
|------|---------|-----------|----------|
| `data/nhs_conditions2.json` | Medical conditions database | ✅ **YES** | ❌ None - diagnosis will fail without this |
| `data/full_medical_index.faiss` | FAISS vector index | ⚠️ Optional | Falls back to JSON search |
| `data/full_medical_metadata.pkl` | FAISS metadata | ⚠️ Optional | Falls back to JSON search |
| `data/fast_medical_index.faiss` | Fast FAISS index | ⚠️ Optional | Falls back to full index or JSON |
| `data/fast_medical_metadata.pkl` | Fast FAISS metadata | ⚠️ Optional | Falls back to full index or JSON |

## ⚠️ Optional Files (Documentation & Testing)

These files are **NOT required** for the agent to function, but are useful:

- `README.md` - General documentation
- `ARCHITECTURE.md` - Architecture documentation
- `DIAGNOSIS_GUIDE.md` - Diagnosis guide
- `QUICK_REFERENCE.md` - Quick reference
- `QUICKSTART.md` - Quick start guide
- `README_NODES.md` - Nodes documentation
- `INDEPENDENCE.md` - Independence documentation
- `test_*.py` - Test files
- `demo_*.py` - Demo files

## 🔧 External Dependencies

### Python Packages (Required)

```bash
pip install httpx geopy openai groq sentence-transformers faiss-cpu
```

| Package | Purpose | Required? |
|---------|---------|-----------|
| `httpx` | HTTP client for API calls | ✅ YES |
| `geopy` | Geocoding and location services | ✅ YES |
| `openai` or `groq` | LLM client for symptom extraction and diagnosis | ✅ YES (one of them) |
| `sentence-transformers` | For FAISS embeddings | ⚠️ Optional (only if using FAISS) |
| `faiss-cpu` or `faiss-gpu` | Vector similarity search | ⚠️ Optional (only if using FAISS) |

### Environment Variables

```bash
# Required (at least one LLM API key)
GROQ_API_KEY="gsk_..."                    # Optional - for Groq LLM
HEALTHCARE_API_KEY="sk-..."               # Optional - for OpenAI-compatible API
HEALTHCARE_BASE_URL="https://..."        # Optional - for OpenAI-compatible API
```

## 📋 Minimum Required Setup

For the agent to work with **basic functionality**:

```
agents/triage_agent/
├── __init__.py
├── agent.py
├── nodes.py
├── diagnosis_utils.py
├── diagnosis_logic.py
├── knowledge_base.py
├── workflow.py
└── data/
    └── nhs_conditions2.json    # ✅ REQUIRED
```

## 🚀 Recommended Setup (Full Performance)

For **optimal performance** with FAISS:

```
agents/triage_agent/
├── __init__.py
├── agent.py
├── nodes.py
├── diagnosis_utils.py
├── diagnosis_logic.py
├── knowledge_base.py
├── workflow.py
└── data/
    ├── nhs_conditions2.json           # ✅ REQUIRED
    ├── full_medical_index.faiss       # ✅ RECOMMENDED
    ├── full_medical_metadata.pkl      # ✅ RECOMMENDED
    ├── fast_medical_index.faiss       # ⚠️ OPTIONAL
    └── fast_medical_metadata.pkl      # ⚠️ OPTIONAL
```

## ❌ What You DON'T Need

The following are **NOT required** (agent is independent):

- ❌ `triage/` directory (any files from it)
- ❌ NER model files (`triage/models/symptom_ner_spacy/`)
- ❌ Symptom dictionary (`triage/data/symptom_dict.json`)
- ❌ Any files from `triage/src/` or `triage/diag/` (code files)

## ✅ Verification Checklist

To verify your setup is complete:

- [ ] All 7 core Python files exist
- [ ] `data/nhs_conditions2.json` exists
- [ ] At least one LLM API key is set (GROQ_API_KEY or HEALTHCARE_API_KEY)
- [ ] Required Python packages are installed
- [ ] Agent can import without errors

## 🔍 Quick Test

```python
# Test if agent can be imported
from agents.triage_agent import triage_agent

# Test if data files are accessible
from agents.triage_agent.diagnosis_utils import retrieve_conditions_faiss
result = retrieve_conditions_faiss("fever headache", top_k=5)
print(f"Found {len(result)} conditions")  # Should return results
```

## 📝 Summary

**Minimum Required:**
- 7 Python files (core modules)
- 1 data file: `data/nhs_conditions2.json`
- Python packages: `httpx`, `geopy`, `openai` or `groq`

**For Best Performance:**
- Add FAISS files to `data/` directory
- Install `sentence-transformers` and `faiss-cpu`

**Total Size (Minimum):**
- Core files: ~500 KB
- `nhs_conditions2.json`: ~5-10 MB
- **Total: ~5-10 MB**

**Total Size (With FAISS):**
- Core files: ~500 KB
- Data files: ~50-100 MB
- **Total: ~50-100 MB**


