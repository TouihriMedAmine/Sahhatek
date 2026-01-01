# Wound Analyzer Model Loading - Complete Call Chain

## 1. File Location
```
agents/wound_analyzer/wound_classifier_weights.pth
```

## 2. Environment Variable Configuration
```
File: .env
Variable: WOUND_MODEL_PATH
Current Value: agents/wound_analyzer/wound_classifier_weights.pth
Default Value: /kaggle/working/wound_classifier_weights.pth
```

## 3. Complete Call Chain

### Entry Point: `wound_analyzer_agent()` (agent.py:142-170)
```python
@trace_agent_node
def wound_analyzer_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Main agent for wound analysis"""
    # Extract image data
    image_data = state.get("metadata", {}).get("image")
    
    if image_data:
        # Call analyze_wound_image with image
        output = analyze_wound_image(...)
    else:
        # No image, use fallback
        output = handle_no_image_provided(...)
```

### Step 1: `analyze_wound_image()` (agent.py:176-226)
```python
def analyze_wound_image(user_input: str, image_data: Dict) -> str:
    """Analyze wound from image"""
    
    # Decode image from base64
    is_valid, image_bytes, error = decode_base64_image(image_base64)
    
    if FASTAI_AVAILABLE and image_bytes:
        # Call inference with image bytes
        analysis = infer_wound_classification(image_bytes, user_input)
    else:
        # Fallback mode
        analysis = analyze_with_fallback(user_input)
```

### Step 2: `infer_wound_classification()` (agent.py:229-301)
```python
def infer_wound_classification(image_bytes: bytes, user_input: str) -> str:
    """Run PyTorch model inference on wound image"""
    
    # Load image from bytes
    img = Image.open(BytesIO(image_bytes))
    
    # THIS IS WHERE MODEL IS LOADED
    model = load_wound_classifier_model()  # <-- MODEL LOADING CALL
    
    if model is None:
        return analyze_with_fallback(user_input)
    
    # Preprocess image
    input_tensor = preprocess(img)
    
    # Run inference
    with torch.no_grad():
        output = model(input_tensor)
        # Get predictions
        pred_class_idx = torch.argmax(output).item()
        confidence = float(confidence_scores[pred_class_idx])
    
    # Get class name
    pred_class_name = CLASS_NAMES[pred_class_idx]
    
    # Build report
    report = build_wound_analysis_report(...)
```

### Step 3: `load_wound_classifier_model()` (agent.py:304-345)
```python
def load_wound_classifier_model():
    """Load FastAI wound classifier model"""
    
    # 1. GET MODEL PATH FROM ENVIRONMENT
    model_path = os.getenv('WOUND_MODEL_PATH', 
                           '/kaggle/working/wound_classifier_weights.pth')
    # Result: 'agents/wound_analyzer/wound_classifier_weights.pth'
    
    # 2. CHECK IF FILE EXISTS
    if not os.path.exists(model_path):
        logger.warning(f"Model not found at {model_path}")
        return None
    
    # 3. LOAD WEIGHTS FROM .PTH FILE
    state_dict = torch.load(model_path, map_location='cpu')
    # Loads: ResNet34 weights (10 output classes for wounds)
    
    # 4. CREATE MODEL ARCHITECTURE
    model = resnet34(weights=None)  # ResNet34 backbone
    num_features = model.fc.in_features  # 512
    model.fc = torch.nn.Linear(num_features, len(CLASS_NAMES))  # 512 -> 10
    
    # 5. LOAD WEIGHTS INTO MODEL
    model.load_state_dict(state_dict, strict=False)
    # strict=False ignores shape mismatches from FastAI format
    
    # 6. SET EVALUATION MODE
    model.eval()  # Disable dropout, batch norm
    
    # 7. MOVE TO GPU IF AVAILABLE
    if torch.cuda.is_available():
        model.to('cuda')
    
    # 8. RETURN LOADED MODEL
    return model
```

## 4. Data Flow

```
User Upload Image (Browser)
        ↓
Base64 Encode in JavaScript
        ↓
Send JSON: { "content": "...", "image": "data:image/jpeg;base64,..." }
        ↓
Django View (agents/views.py:165)
        ↓
Extract: image_data = data.get("image")
        ↓
Pass to LangGraph: state["metadata"]["image"] = image_data
        ↓
wound_analyzer_agent()
        ↓
analyze_wound_image(image_data)
        ↓
Decode Base64: image_bytes
        ↓
infer_wound_classification(image_bytes)
        ↓
load_wound_classifier_model()  <-- LOADS .PTH FILE
        ↓
torch.load(model_path, map_location='cpu')
        ↓
model.load_state_dict(state_dict, strict=False)
        ↓
model.eval()
        ↓
Run Inference: output = model(input_tensor)
        ↓
Get Predictions
        ↓
Build Report
        ↓
Return Analysis to User
```

## 5. Model File Details

### File Information
```
Location: agents/wound_analyzer/wound_classifier_weights.pth
Size: ~87 MB (ResNet34 trained on 10 wound classes)
Format: PyTorch state_dict
Architecture: ResNet34 (ImageNet backbone + custom 10-class head)
```

### Classes (10 Wound Types)
```
0: Abrasions
1: Burns
2: Bruises
3: Cut
4: Diabetic Wounds
5: Laceration
6: Pressure Wounds
7: Surgical Wounds
8: Venous Wounds
9: Normal
```

## 6. Key Code Sections

### Loading the Model
**File**: [agents/wound_analyzer/agent.py](agents/wound_analyzer/agent.py#L304)
**Lines**: 304-345

```python
state_dict = torch.load(model_path, map_location='cpu')
model.load_state_dict(state_dict, strict=False)
```

### Using the Model
**File**: [agents/wound_analyzer/agent.py](agents/wound_analyzer/agent.py#L245)
**Lines**: 245, 265-275

```python
model = load_wound_classifier_model()
...
with torch.no_grad():
    output = model(input_tensor)
    confidence_scores = torch.nn.functional.softmax(output, dim=1)
```

### Environment Variable
**File**: [.env](.env)
**Line**: Last line

```
WOUND_MODEL_PATH=agents/wound_analyzer/wound_classifier_weights.pth
```

## 7. Error Handling

| Error | Cause | Fallback |
|-------|-------|----------|
| Model not found | WOUND_MODEL_PATH wrong | Returns None → analyze_with_fallback() |
| State dict mismatch | FastAI format | strict=False ignores extra keys |
| CUDA not available | No GPU | Runs on CPU |
| Load failed | Corrupted file | catch Exception → return None |

## 8. Testing the Model

### Local Test Script
```bash
python test_wound_analyzer_local.py
```

**Output**:
```
[OK] Found image: c:\Users\Houss\Downloads\laseration (16).jpg
[OK] Base64 length: 47511 characters
[RUN] Invoking Wound Analyzer Agent...
✅ Prediction: Venous Wounds (confidence: 99.1%)
```

## 9. Summary

| Component | Location | Purpose |
|-----------|----------|---------|
| **Model File** | `agents/wound_analyzer/wound_classifier_weights.pth` | Contains trained ResNet34 weights |
| **Loader** | `agent.py:304-345` | `load_wound_classifier_model()` function |
| **Caller** | `agent.py:245` | `infer_wound_classification()` calls loader |
| **Environment** | `.env` | `WOUND_MODEL_PATH` variable |
| **Entry** | `agent.py:142` | `wound_analyzer_agent()` entry point |

The `.pth` file is only loaded **once per inference** when `infer_wound_classification()` is called with image data.
