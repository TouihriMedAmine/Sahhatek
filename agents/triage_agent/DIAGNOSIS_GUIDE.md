# How to Add Your Diagnosis Logic

## 📍 Exact Location

Your diagnosis logic goes in **`agents/triage_agent/nodes.py`** in the **`diagnosis_node()`** function.

**File**: `agents/triage_agent/nodes.py`  
**Function**: `diagnosis_node()`  
**Lines**: Approximately **133-168**

## 🔧 Current Code (Placeholder)

```python
def diagnosis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Identify disease from symptoms.
    This is a placeholder - user will add logic later.
    
    Expected input: symptoms (list), negative_symptoms (list)
    Expected output: disease (str), severity (str), confidence (float)
    """
    logger.info("🩺 DIAGNOSIS NODE: Identifying disease from symptoms")
    
    try:
        symptoms = state.get("symptoms", [])
        negative_symptoms = state.get("negative_symptoms", [])
        
        # TODO: User will add diagnosis logic here
        # For now, return placeholder
        logger.info("⚠️ Diagnosis node is a placeholder - add logic here")
        
        # Placeholder return
        return {
            "disease": "unknown",
            "severity": "moderate",
            "confidence": 0.5,
            "current_agent": "diagnosis",
            "agent_output": "Diagnosis node placeholder - add logic here"
        }
    except Exception as e:
        logger.error(f"Error in diagnosis node: {e}", exc_info=True)
        return {
            "disease": "unknown",
            "severity": "moderate",
            "confidence": 0.5,
            "current_agent": "diagnosis",
            "agent_output": f"Error in diagnosis: {str(e)}"
        }
```

## ✏️ What to Replace

Replace the **TODO section** (lines ~147-158) with your diagnosis logic:

```python
# REPLACE THIS SECTION:
# TODO: User will add diagnosis logic here
# For now, return placeholder
logger.info("⚠️ Diagnosis node is a placeholder - add logic here")

# Placeholder return
return {
    "disease": "unknown",
    "severity": "moderate",
    "confidence": 0.5,
    "current_agent": "diagnosis",
    "agent_output": "Diagnosis node placeholder - add logic here"
}

# WITH YOUR LOGIC:
# Example structure:
from your_diagnosis_module import diagnose  # Import your diagnosis function/model

# Call your diagnosis function
diagnosis_result = diagnose(
    symptoms=symptoms,
    negative_symptoms=negative_symptoms,
    # Add any other parameters your function needs
)

# Extract results
disease = diagnosis_result.get("disease", "unknown")
severity = diagnosis_result.get("severity", "moderate")
confidence = diagnosis_result.get("confidence", 0.5)

# Return in the expected format
return {
    "disease": disease,
    "severity": severity,
    "confidence": confidence,
    "current_agent": "diagnosis",
    "agent_output": f"Diagnosed: {disease} (confidence: {confidence:.2f})"
}
```

## 📥 Input Available

The `diagnosis_node()` function receives:

```python
state = {
    "symptoms": ["headache", "fever", "fatigue"],  # Positive symptoms
    "negative_symptoms": ["nausea"],                # Negated symptoms
    "user_input": "I have a headache and fever",    # Original text
    "extraction_result": {...},                    # Full NER extraction result
    # ... other state fields
}
```

## 📤 Output Required

Your function **MUST** return a dictionary with these fields:

```python
{
    "disease": str,        # Disease name (e.g., "flu", "common cold")
    "severity": str,       # "mild", "moderate", or "severe"
    "confidence": float,   # 0.0 to 1.0 (confidence score)
    "current_agent": "diagnosis",  # Keep this
    "agent_output": str    # Optional: diagnostic message
}
```

## 💡 Example Implementations

### Example 1: Simple Rule-Based

```python
def diagnosis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("🩺 DIAGNOSIS NODE: Identifying disease from symptoms")
    
    try:
        symptoms = state.get("symptoms", [])
        negative_symptoms = state.get("negative_symptoms", [])
        
        # Simple rule-based diagnosis
        symptoms_lower = [s.lower() for s in symptoms]
        
        if "fever" in symptoms_lower and "headache" in symptoms_lower:
            disease = "flu"
            severity = "moderate"
            confidence = 0.75
        elif "cough" in symptoms_lower and "sore throat" in symptoms_lower:
            disease = "common cold"
            severity = "mild"
            confidence = 0.65
        else:
            disease = "unknown"
            severity = "moderate"
            confidence = 0.3
        
        return {
            "disease": disease,
            "severity": severity,
            "confidence": confidence,
            "current_agent": "diagnosis",
            "agent_output": f"Diagnosed: {disease}"
        }
    except Exception as e:
        logger.error(f"Error in diagnosis node: {e}", exc_info=True)
        return {
            "disease": "unknown",
            "severity": "moderate",
            "confidence": 0.5,
            "current_agent": "diagnosis",
            "agent_output": f"Error in diagnosis: {str(e)}"
        }
```

### Example 2: Using External Diagnosis Module

```python
def diagnosis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("🩺 DIAGNOSIS NODE: Identifying disease from symptoms")
    
    try:
        symptoms = state.get("symptoms", [])
        negative_symptoms = state.get("negative_symptoms", [])
        
        # Import your diagnosis module
        import sys
        import os
        diagnosis_module_path = os.path.join(os.path.dirname(__file__), "../../../your_diagnosis_directory")
        if diagnosis_module_path not in sys.path:
            sys.path.insert(0, diagnosis_module_path)
        
        from your_diagnosis_model import predict_disease
        
        # Call your diagnosis model
        result = predict_disease(
            symptoms=symptoms,
            negative_symptoms=negative_symptoms
        )
        
        return {
            "disease": result["disease"],
            "severity": result["severity"],
            "confidence": result["confidence"],
            "current_agent": "diagnosis",
            "agent_output": f"Diagnosed: {result['disease']} (confidence: {result['confidence']:.2f})"
        }
    except Exception as e:
        logger.error(f"Error in diagnosis node: {e}", exc_info=True)
        return {
            "disease": "unknown",
            "severity": "moderate",
            "confidence": 0.5,
            "current_agent": "diagnosis",
            "agent_output": f"Error in diagnosis: {str(e)}"
        }
```

### Example 3: Using LLM for Diagnosis

```python
def diagnosis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("🩺 DIAGNOSIS NODE: Identifying disease from symptoms")
    
    try:
        symptoms = state.get("symptoms", [])
        negative_symptoms = state.get("negative_symptoms", [])
        
        from .agent import get_llm_client
        
        client = get_llm_client()
        if client:
            prompt = f"""Based on these symptoms, diagnose the condition:
Positive symptoms: {', '.join(symptoms)}
Negative symptoms: {', '.join(negative_symptoms)}

Respond in format: DISEASE|SEVERITY|CONFIDENCE
Example: flu|moderate|0.85"""
            
            response = client.chat.completions.create(
                model="your-model",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            parts = result_text.split("|")
            
            disease = parts[0].strip() if len(parts) > 0 else "unknown"
            severity = parts[1].strip() if len(parts) > 1 else "moderate"
            confidence = float(parts[2]) if len(parts) > 2 and parts[2].replace(".", "").isdigit() else 0.5
            
            return {
                "disease": disease,
                "severity": severity,
                "confidence": confidence,
                "current_agent": "diagnosis",
                "agent_output": f"Diagnosed: {disease}"
            }
        else:
            # Fallback
            return {
                "disease": "unknown",
                "severity": "moderate",
                "confidence": 0.5,
                "current_agent": "diagnosis",
                "agent_output": "Diagnosis service unavailable"
            }
    except Exception as e:
        logger.error(f"Error in diagnosis node: {e}", exc_info=True)
        return {
            "disease": "unknown",
            "severity": "moderate",
            "confidence": 0.5,
            "current_agent": "diagnosis",
            "agent_output": f"Error in diagnosis: {str(e)}"
        }
```

## ✅ Testing Your Diagnosis Node

After adding your logic, test it:

```python
from agents.triage_agent.nodes import diagnosis_node

state = {
    "symptoms": ["headache", "fever"],
    "negative_symptoms": ["nausea"]
}

result = diagnosis_node(state)
print(f"Disease: {result['disease']}")
print(f"Severity: {result['severity']}")
print(f"Confidence: {result['confidence']}")
```

Or run the full test:

```bash
python agents/triage_agent/test_nodes.py
```

## 📝 Important Notes

1. **Always return the required fields**: `disease`, `severity`, `confidence`, `current_agent`
2. **Handle errors gracefully**: Wrap your logic in try/except and return fallback values
3. **Log important steps**: Use `logger.info()` to track diagnosis flow
4. **Preserve state**: Don't modify other state fields unnecessarily
5. **Confidence score**: Should be between 0.0 and 1.0 (higher = more confident)

## 🎯 Next Steps

1. Open `agents/triage_agent/nodes.py`
2. Find the `diagnosis_node()` function (around line 133)
3. Replace the TODO section with your diagnosis logic
4. Test using `test_nodes.py`
5. The workflow will automatically use your diagnosis!

