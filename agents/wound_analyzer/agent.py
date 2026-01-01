# agents/wound_analyzer/agent.py
from typing import Dict, Any, List, Tuple, Optional
import base64
import logging
import os
import torch
from pathlib import Path
from PIL import Image
from io import BytesIO

# FastAI imports
try:
    from fastai.vision.all import *
    FASTAI_AVAILABLE = True
except ImportError:
    FASTAI_AVAILABLE = False

from agents.state import AgentState
from agents.langsmith_decorators import trace_agent_node, add_metadata_to_state
from agents.wound_analyzer.service import (
    validate_image_data,
    decode_base64_image,
    preprocess_image_for_fastai,
    classify_wound_severity,
    check_infection_indicators,
    get_care_instructions
)

logger = logging.getLogger(__name__)

if not FASTAI_AVAILABLE:
    logger.warning("FastAI not available - using fallback responses")

# ============================================================
# WOUND CLASSIFICATION CONFIGURATION
# ============================================================

CLASS_NAMES = [
    'Abrasions', 'Burns', 'Bruises', 'Cut', 'Diabetic Wounds',
    'Laceration', 'Pressure Wounds', 'Surgical Wounds', 'Venous Wounds', 'Normal'
]

BASE_SEVERITY = {
    'Normal': 0,
    'Abrasions': 1,
    'Burns': 3,
    'Bruises': 1,
    'Cut': 2,
    'Diabetic Wounds': 3,
    'Laceration': 2,
    'Pressure Wounds': 3,
    'Surgical Wounds': 2,
    'Venous Wounds': 2
}

AREA_THRESHOLDS = {
    'Abrasions': [0.01, 0.05],
    'Burns': [0.005, 0.02],
    'Bruises': [0.01, 0.05],
    'Cut': [0.01, 0.03],
    'Diabetic Wounds': [0.005, 0.02],
    'Laceration': [0.01, 0.03],
    'Pressure Wounds': [0.005, 0.02],
    'Surgical Wounds': [0.005, 0.02],
    'Venous Wounds': [0.005, 0.02],
    'Normal': [0, 0]
}

SEVERITY_LEVELS = {
    0: 'Normal',
    1: 'Mild',
    2: 'Moderate',
    3: 'Severe',
    4: 'Emergency'
}

CARE_INSTRUCTIONS_MAP = {
    'Normal': {
        'type': 'No visible wound',
        'care': ['Maintain skin health', 'Monitor for changes'],
        'emergency_signs': []
    },
    'Abrasions': {
        'type': 'Surface skin damage',
        'care': ['Gently clean with water', 'Apply antibiotic ointment', 'Cover with sterile gauze', 'Change dressing daily'],
        'emergency_signs': ['Deep scratches', 'Embedded debris', 'Signs of infection']
    },
    'Burns': {
        'type': 'Thermal injury',
        'care': ['Cool with running water (10-20 minutes)', 'Remove tight items', 'Apply burn ointment', 'Avoid popping blisters'],
        'emergency_signs': ['Charred or white skin', 'Large blistered areas', 'Burns on face/hands/genitals']
    },
    'Bruises': {
        'type': 'Blunt trauma injury',
        'care': ['Apply ice (15 minutes)', 'Keep elevated', 'Rest the area', 'Monitor for swelling'],
        'emergency_signs': ['Increasing swelling', 'Loss of function', 'Severe pain']
    },
    'Cut': {
        'type': 'Clean break in skin',
        'care': ['Stop bleeding with pressure', 'Clean with water and soap', 'Apply antibiotic ointment', 'Use sterile dressing'],
        'emergency_signs': ['Won\'t stop bleeding', 'Edges won\'t stay together', 'Possible tetanus exposure']
    },
    'Diabetic Wounds': {
        'type': 'Diabetic ulcer or wound',
        'care': ['Keep blood sugar controlled', 'Clean with saline daily', 'Use prescribed medications', 'Monitor blood flow'],
        'emergency_signs': ['Signs of infection', 'Increasing size', 'Odor or discharge', 'Fever']
    },
    'Laceration': {
        'type': 'Jagged or torn wound',
        'care': ['Stop bleeding with pressure', 'Clean thoroughly', 'May need stitches', 'Keep clean and dry'],
        'emergency_signs': ['Deep or gaping', 'Won\'t stop bleeding', 'Possible nerve/tendon damage']
    },
    'Pressure Wounds': {
        'type': 'Pressure ulcer (bedsore)',
        'care': ['Relieve pressure regularly', 'Keep clean and dry', 'Apply wound dressing', 'Improve nutrition'],
        'emergency_signs': ['Increasing depth', 'Signs of infection', 'Blackened tissue', 'Foul odor']
    },
    'Surgical Wounds': {
        'type': 'Post-operative incision',
        'care': ['Keep dry and clean', 'Follow surgeon\'s instructions', 'Don\'t remove stitches', 'Watch for infection'],
        'emergency_signs': ['Opening at incision', 'Excessive drainage', 'Fever', 'Increasing redness']
    },
    'Venous Wounds': {
        'type': 'Venous insufficiency ulcer',
        'care': ['Elevate leg frequently', 'Wear compression stockings', 'Keep clean and moist', 'Improve circulation'],
        'emergency_signs': ['Rapid growth', 'Signs of infection', 'Severe pain', 'Loss of feeling']
    }
}


@trace_agent_node("wound_analyzer", "🩹_WoundAnalyzer_Processing")
def wound_analyzer_agent(state: AgentState) -> AgentState:
    """
    Wound Analyzer Agent using Computer Vision
    
    Analyzes images of wounds, rashes, and skin conditions.
    - Receives image data from the frontend
    - Processes and analyzes the image
    - Provides medical assessment and recommendations
    - Routes to orientation if urgent referral needed
    """
    user_input: str = (state.get("user_input") or "").strip()
    messages: List[Dict[str, str]] = state.get("messages") or []
    metadata: Dict[str, Any] = state.get("metadata") or {}
    
    state["current_agent"] = "wound_analyzer"
    state["next_agent"] = None
    
    # Initialize wound analysis metadata
    metadata.setdefault("wound_analysis", {})
    
    # Check if image data is present
    # Handle both dict format and direct base64 string
    image_data = metadata.get("image")
    
    # Normalize image_data to dict format
    if isinstance(image_data, str):
        # Direct base64 string from frontend
        image_data = {"data": image_data}
    elif not isinstance(image_data, dict):
        image_data = {}
    
    has_image = bool(image_data.get("data") or image_data.get("url"))
    
    # Process based on whether we have an image or just text
    if has_image:
        output = analyze_wound_image(user_input, image_data, metadata)
    else:
        output = handle_no_image_provided(user_input)
    
    state["agent_output"] = output
    metadata["wound_analysis"]["processed"] = True
    state["metadata"] = metadata
    
    # Add message to conversation
    messages.append({
        "role": "assistant",
        "content": output,
        "agent": "wound_analyzer"
    })
    state["messages"] = messages
    
    return state


def analyze_wound_image(user_input: str, image_data: Dict, metadata: Dict) -> str:
    """
    Analyze wound image using FastAI classifier model
    
    Args:
        user_input: User's description of the wound
        image_data: Image data dict with 'data' (base64) or 'url'
        metadata: Request metadata
    
    Returns:
        Analysis output string
    """
    try:
        # Extract image information
        image_url = image_data.get("url")
        image_base64 = image_data.get("data")
        
        logger.info(f"🩹 Analyzing wound image. User input: {user_input}")
        
        # Decode image
        if image_base64:
            is_valid, image_bytes, error = decode_base64_image(image_base64)
            if not is_valid:
                return f"❌ {error}"
        elif image_url:
            image_bytes = None  # TODO: Download from URL
        else:
            return handle_no_image_provided(user_input)
        
        # Get model inference
        if FASTAI_AVAILABLE and image_bytes:
            analysis = infer_wound_classification(image_bytes, user_input)
        else:
            analysis = analyze_with_fallback(user_input)
        
        return analysis
        
    except Exception as e:
        logger.error(f"❌ Error analyzing wound image: {str(e)}")
        return f"⚠️ I encountered an error while analyzing the image. Please try again or describe the wound in more detail.\n\nError: {str(e)}"


def infer_wound_classification(image_bytes: bytes, user_input: str) -> str:
    """
    Run PyTorch model inference on wound image
    
    Args:
        image_bytes: Raw image bytes
        user_input: User description of wound
    
    Returns:
        Formatted analysis result
    """
    try:
        # Load image from bytes
        img = Image.open(BytesIO(image_bytes))
        img = img.convert('RGB')
        
        # Get or load model
        model = load_wound_classifier_model()
        if model is None:
            return analyze_with_fallback(user_input)
        
        # Preprocess image for ResNet34
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
        
        # Move to GPU if available
        if torch.cuda.is_available():
            input_batch = input_batch.to('cuda')
            model = model.to('cuda')
        
        # Get prediction
        with torch.no_grad():
            output = model(input_batch)
            probs = torch.nn.functional.softmax(output, dim=1)
            confidence_scores = probs[0]
            pred_class_idx = torch.argmax(confidence_scores).item()
            confidence = float(confidence_scores[pred_class_idx])
        
        # Get predicted class name
        pred_class_name = CLASS_NAMES[pred_class_idx]
        
        # Calculate severity
        severity_level = BASE_SEVERITY.get(pred_class_name, 0)
        severity_text = SEVERITY_LEVELS.get(severity_level, 'Unknown')
        
        # Build report
        report = build_wound_analysis_report(
            wound_type=pred_class_name,
            severity=severity_level,
            severity_text=severity_text,
            confidence=confidence,
            user_description=user_input
        )
        
        logger.info(f"✅ Prediction: {pred_class_name} (confidence: {confidence:.2%})")
        return report
        
    except Exception as e:
        logger.error(f"Error in model inference: {str(e)}")
        return analyze_with_fallback(user_input)


def load_wound_classifier_model():
    """
    Load FastAI wound classifier model
    
    Returns:
        Loaded learner object or None if not available
    """
    try:
        model_path = os.getenv('WOUND_MODEL_PATH', 'agents/wound_analyzer/wound_classifier_weights.pth')
        
        if not os.path.exists(model_path):
            logger.warning(f"Model not found at {model_path}")
            return None
        
        # Load FastAI learner state dict directly
        # Create a fastai learner and load the saved weights
        from fastai.vision.all import create_cnn_model, resnet34, cnn_learner
        
        # Load state dict as-is (FastAI format)
        state_dict = torch.load(model_path, map_location='cpu')
        logger.info(f"Loaded FastAI state dict with {len(state_dict)} keys")
        
        # Create dummy DataLoaders for the learner (FastAI requires these)
        # We'll create simple empty loaders just for model instantiation
        dls = create_dummy_dataloaders()
        
        # Create learner with the same architecture FastAI used
        try:
            learner = cnn_learner(
                dls, 
                resnet34,
                metrics=accuracy,
                pretrained=False
            )
        except:
            # If cnn_learner fails, create model directly
            logger.info("Creating model directly without cnn_learner")
            model = create_cnn_model(resnet34, 10, custom_head=None)
            model.load_state_dict(state_dict, strict=False)
            model.eval()
            if torch.cuda.is_available():
                model.to('cuda')
            logger.info("✅ Model loaded successfully")
            return model
        
        # Load weights into learner
        learner.model.load_state_dict(state_dict, strict=False)
        learner.model.eval()
        
        if torch.cuda.is_available():
            learner.model.to('cuda')
        
        logger.info("✅ FastAI learner loaded successfully")
        return learner.model
        
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def create_dummy_dataloaders():
    """Create dummy DataLoaders for FastAI learner initialization"""
    try:
        from fastai.vision.all import DataLoaders
        import torch
        from torch.utils.data import DataLoader, TensorDataset
        
        # Create dummy data
        dummy_images = torch.randn(8, 3, 224, 224)
        dummy_labels = torch.arange(10).repeat(1)[:8]
        
        dataset = TensorDataset(dummy_images, dummy_labels)
        loader = DataLoader(dataset, batch_size=2)
        
        # Create DataLoaders object
        dls = DataLoaders(loader, loader)
        dls.c = len(CLASS_NAMES)  # Number of classes
        
        return dls
    except Exception as e:
        logger.warning(f"Could not create dummy dataloaders: {e}")
        return None


def create_fastai_learner():
    """Create empty learner for fallback"""
    return None


def analyze_with_fallback(user_input: str) -> str:
    """
    Fallback analysis when model is unavailable
    """
    return f"""🩹 **Wound Analysis (Model Offline)**

Based on your description: "{user_input}"

I'm running in fallback mode without the AI model. Please ensure:
1. FastAI is installed
2. Model weights are available
3. CUDA/GPU is configured (optional but recommended)

**To enable full analysis:**
- Install dependencies: `pip install fastai torch`
- Set WOUND_MODEL_PATH environment variable
- Restart the service

For now, I recommend:
- Keep the wound clean and dry
- Monitor for signs of infection (redness, warmth, discharge)
- Seek medical attention if symptoms worsen"""


def build_wound_analysis_report(
    wound_type: str,
    severity: int,
    severity_text: str,
    confidence: float,
    user_description: str
) -> str:
    """Build detailed wound analysis report"""
    
    care_info = CARE_INSTRUCTIONS_MAP.get(wound_type, CARE_INSTRUCTIONS_MAP['Normal'])
    
    report = f"""🩹 **AI Wound Analysis Report**

**Classification**: {wound_type}
**Severity Level**: {severity_text} (Level {severity}/4)
**Confidence**: {confidence:.1%}

**Wound Type**: {care_info['type']}

**Description**: {user_description}

**Recommended Care Instructions:**
"""
    for i, instruction in enumerate(care_info['care'], 1):
        report += f"\n{i}. {instruction}"
    
    if care_info['emergency_signs']:
        report += "\n\n**⚠️ EMERGENCY SIGNS - Seek immediate medical attention if:**"
        for sign in care_info['emergency_signs']:
            report += f"\n• {sign}"
    
    report += f"""

**Severity Details**: {SEVERITY_LEVELS.get(severity, 'Unknown')} wound
- Monitor closely for infection
- Keep records of wound appearance
- Follow care instructions strictly

**Next Steps:**
1. Clean the wound according to instructions
2. Monitor daily for changes
3. Change dressing as recommended
4. Seek professional help if conditions worsen

⚠️ **Disclaimer**: This analysis is for informational purposes only. 
Always consult a healthcare professional for serious wounds.
"""
    
    return report


def handle_no_image_provided(user_input: str) -> str:
    """Handle case when no image is provided"""
    return f"""🩹 **Wound Analysis Assistant**

I noticed you didn't upload an image. To provide the best analysis, please:

1. **Upload a clear image** of the wound, rash, or skin condition
2. **Describe what you see:** location, size, color, texture
3. **Tell me about symptoms:** pain level, itching, discharge, etc.
4. **Mention timeline:** How long has this been present?

**What I can analyze:**
- Cuts and lacerations
- Burns and thermal injuries
- Rashes and skin conditions
- Abrasions and scrapes
- Surgical wounds
- Diabetic foot wounds

**Please upload an image** and I'll provide a detailed assessment.

⚠️ **Emergency:** Call emergency services if there's:
- Uncontrolled bleeding
- Signs of severe infection
- Deep wounds with exposed tissue
- Wounds from contaminated objects"""


@trace_agent_node("wound_severity_router", "🚨_WoundSeverity_Router")
def wound_severity_router(state: AgentState) -> AgentState:
    """
    Routes to orientation agent if wound analysis indicates emergency
    """
    metadata: Dict[str, Any] = state.get("metadata") or {}
    wound_analysis = metadata.get("wound_analysis", {})
    
    # Check if severe condition detected
    severity_indicators = [
        "emergency",
        "severe",
        "urgent",
        "hospital",
        "infection",
        "uncontrolled bleeding"
    ]
    
    agent_output = (state.get("agent_output") or "").lower()
    
    if any(indicator in agent_output for indicator in severity_indicators):
        state["next_agent"] = "orientation"
        state["wound_analysis_severity"] = "urgent"
    else:
        state["wound_analysis_severity"] = "routine"
    
    return state