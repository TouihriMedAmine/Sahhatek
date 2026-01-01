# agents/wound_analyzer/service.py
"""Service functions for wound analysis using FastAI"""
import logging
from typing import Dict, Any, Tuple, Optional
import base64
import os
from PIL import Image
from io import BytesIO

try:
    from fastai.vision.all import *
    import torch
    FASTAI_AVAILABLE = True
except ImportError:
    FASTAI_AVAILABLE = False

logger = logging.getLogger(__name__)


def validate_image_data(image_data: Dict) -> Tuple[bool, str]:
    """
    Validate image data before processing
    
    Args:
        image_data: Dict with 'data' (base64) or 'url'
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not image_data:
        return False, "No image data provided"
    
    # Check for base64 data
    if "data" in image_data:
        data = image_data["data"]
        if len(data) > 20 * 1024 * 1024:  # 20MB limit
            return False, "Image too large (max 20MB)"
        return True, ""
    
    # Check for URL
    if "url" in image_data:
        url = image_data["url"]
        if not isinstance(url, str) or len(url) < 10:
            return False, "Invalid image URL"
        return True, ""
    
    return False, "Image must contain 'data' (base64) or 'url'"


def decode_base64_image(base64_data: str) -> Tuple[bool, Optional[bytes], str]:
    """
    Decode base64 image data
    
    Args:
        base64_data: Base64 encoded image string
    
    Returns:
        Tuple of (success, image_bytes, error_message)
    """
    try:
        # Remove data URL prefix if present
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
        
        image_bytes = base64.b64decode(base64_data)
        
        # Validate it's a valid image
        img = Image.open(BytesIO(image_bytes))
        img.verify()  # This closes the image, so we need to reopen
        
        return True, image_bytes, ""
    except Exception as e:
        logger.error(f"Failed to decode base64: {str(e)}")
        return False, None, f"Failed to decode image: {str(e)}"


def preprocess_image_for_fastai(image_bytes: bytes) -> Tuple[bool, Any, str]:
    """
    Preprocess image for FastAI model
    
    Args:
        image_bytes: Raw image bytes
    
    Returns:
        Tuple of (success, pil_image, error_message)
    """
    try:
        # Open image from bytes
        img = Image.open(BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        return True, img, ""
    except Exception as e:
        logger.error(f"Failed to preprocess image: {str(e)}")
        return False, None, f"Failed to process image: {str(e)}"


def classify_wound_severity(pred_class: str, base_severity: Dict) -> Tuple[int, str]:
    """
    Classify wound severity based on prediction
    
    Args:
        pred_class: Predicted wound class name
        base_severity: Severity mapping dictionary
    
    Returns:
        Tuple of (severity_level, severity_text)
    """
    severity_levels = {
        0: 'Normal',
        1: 'Mild',
        2: 'Moderate',
        3: 'Severe',
        4: 'Emergency'
    }
    
    severity = base_severity.get(pred_class, 0)
    
    if severity >= 3:
        return severity, severity_levels.get(severity, 'Unknown')
    elif severity >= 2:
        return severity, severity_levels.get(severity, 'Unknown')
    elif severity >= 1:
        return severity, severity_levels.get(severity, 'Unknown')
    else:
        return 0, 'Normal'


def check_infection_indicators(pred_class: str, user_description: str = "") -> Tuple[bool, list]:
    """
    Check for infection indicators based on wound type
    
    Args:
        pred_class: Predicted wound class
        user_description: User's description of the wound
    
    Returns:
        Tuple of (has_infection_risk, list_of_indicators)
    """
    infection_indicators = []
    has_risk = False
    
    # Infection risk by wound type
    high_risk_wounds = [
        'Diabetic Wounds',
        'Venous Wounds',
        'Pressure Wounds',
        'Laceration'
    ]
    
    if pred_class in high_risk_wounds:
        has_risk = True
        infection_indicators.append(f"'{pred_class}' are prone to infection")
    
    # Check user description for infection keywords
    if user_description:
        infection_keywords = [
            'red', 'warm', 'swelling', 'pus', 'discharge',
            'odor', 'smell', 'pain', 'oozing', 'yellow',
            'green', 'infected'
        ]
        
        desc_lower = user_description.lower()
        for keyword in infection_keywords:
            if keyword in desc_lower:
                has_risk = True
                infection_indicators.append(f"Reported: {keyword}")
    
    return has_risk, infection_indicators


def get_care_instructions(wound_type: str, care_map: Dict) -> Dict[str, Any]:
    """
    Get care instructions for wound type
    
    Args:
        wound_type: Type of wound
        care_map: Care instructions mapping
    
    Returns:
        Care instructions dictionary
    """
    return care_map.get(
        wound_type,
        care_map.get('Normal', {
            'type': 'Unknown wound',
            'care': ['Seek professional medical attention'],
            'emergency_signs': ['Any wound that doesn\'t improve']
        })
    )


def validate_fastai_installation() -> Tuple[bool, str]:
    """
    Check if FastAI is properly installed and GPU is available
    
    Returns:
        Tuple of (is_ready, status_message)
    """
    if not FASTAI_AVAILABLE:
        return False, "FastAI not installed. Run: pip install fastai"
    
    try:
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            return True, f"✅ FastAI ready with GPU: {gpu_name}"
        else:
            return True, "✅ FastAI ready (CPU mode)"
    except Exception as e:
        return False, f"FastAI check failed: {str(e)}"


def get_model_info() -> Dict[str, Any]:
    """Get information about the wound classifier model"""
    return {
        'architecture': 'ResNet34',
        'framework': 'FastAI',
        'num_classes': 10,
        'classes': [
            'Abrasions', 'Burns', 'Bruises', 'Cut', 'Diabetic Wounds',
            'Laceration', 'Pressure Wounds', 'Surgical Wounds', 'Venous Wounds', 'Normal'
        ],
        'input_size': '224x224',
        'pretrained': True,
        'gpu_enabled': torch.cuda.is_available() if FASTAI_AVAILABLE else False
    }



def validate_image_data(image_data: Dict) -> Tuple[bool, str]:
    """
    Validate image data before processing
    
    Args:
        image_data: Dict with 'data' (base64) or 'url'
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not image_data:
        return False, "No image data provided"
    
    # Check for base64 data
    if "data" in image_data:
        data = image_data["data"]
        if len(data) > 20 * 1024 * 1024:  # 20MB limit
            return False, "Image too large (max 20MB)"
        return True, ""
    
    # Check for URL
    if "url" in image_data:
        url = image_data["url"]
        if not isinstance(url, str) or len(url) < 10:
            return False, "Invalid image URL"
        return True, ""
    
    return False, "Image must contain 'data' (base64) or 'url'"


def decode_base64_image(base64_data: str) -> Tuple[bool, bytes | None, str]:
    """
    Decode base64 image data
    
    Args:
        base64_data: Base64 encoded image string
    
    Returns:
        Tuple of (success, image_bytes, error_message)
    """
    try:
        # Remove data URL prefix if present
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
        
        image_bytes = base64.b64decode(base64_data)
        return True, image_bytes, ""
    except Exception as e:
        logger.error(f"Failed to decode base64: {str(e)}")
        return False, None, f"Failed to decode image: {str(e)}"


def classify_wound_severity(analysis_result: Dict) -> str:
    """
    Classify wound severity based on analysis
    
    Args:
        analysis_result: Vision API analysis result
    
    Returns:
        Severity level: 'mild', 'moderate', 'severe', 'emergency'
    """
    # TODO: Implement logic based on actual vision API response
    severity_indicators = analysis_result.get("severity", 0)
    
    if severity_indicators >= 0.8:
        return "emergency"
    elif severity_indicators >= 0.6:
        return "severe"
    elif severity_indicators >= 0.4:
        return "moderate"
    else:
        return "mild"


def build_wound_report(
    wound_type: str,
    severity: str,
    infection_risk: bool,
    recommendations: list,
    emergency_signs: list
) -> str:
    """Build formatted wound analysis report"""
    
    report = f"""
🩹 **Medical Wound Analysis Report**

**Classification:** {wound_type}
**Severity Level:** {severity.upper()}
**Infection Risk:** {'⚠️ Elevated' if infection_risk else '✅ Low'}

**Recommendations:**
"""
    for i, rec in enumerate(recommendations, 1):
        report += f"\n{i}. {rec}"
    
    if emergency_signs:
        report += "\n\n**⚠️ EMERGENCY SIGNS - Seek immediate medical attention if:**"
        for sign in emergency_signs:
            report += f"\n• {sign}"
    
    return report


def get_care_instructions(wound_type: str) -> Dict[str, Any]:
    """Get standard care instructions for wound type"""
    
    care_guide = {
        "cut": {
            "immediate": [
                "Stop bleeding with direct pressure (10-15 minutes)",
                "Clean with running water",
                "Apply antibiotic ointment"
            ],
            "ongoing": [
                "Change dressing daily",
                "Keep clean and dry",
                "Monitor for infection"
            ],
            "emergency_signs": [
                "Won't stop bleeding after 15 minutes",
                "Edges won't stay together",
                "Possible tetanus exposure"
            ]
        },
        "burn": {
            "immediate": [
                "Cool with running water (10-20 minutes)",
                "Remove tight items",
                "Cover with clean cloth"
            ],
            "ongoing": [
                "Use burn ointment or aloe vera",
                "Keep clean and protected",
                "Avoid popping blisters"
            ],
            "emergency_signs": [
                "Charred or white/brown skin",
                "Blistering over large area",
                "Exposure to face, hands, or genitals"
            ]
        },
        "rash": {
            "immediate": [
                "Avoid scratching",
                "Keep area clean",
                "Use cool compress"
            ],
            "ongoing": [
                "Identify and avoid trigger",
                "Keep skin moisturized",
                "Wear soft clothing"
            ],
            "emergency_signs": [
                "Spreading rapidly",
                "Fever or chills present",
                "Difficulty breathing or swallowing"
            ]
        },
        "abrasion": {
            "immediate": [
                "Clean gently with water",
                "Remove embedded debris",
                "Air dry or cover loosely"
            ],
            "ongoing": [
                "Keep clean and moist",
                "Apply antibiotic ointment",
                "Protect from friction"
            ],
            "emergency_signs": [
                "Deep scratching or embedding",
                "Signs of infection developing",
                "Significant pain or swelling"
            ]
        }
    }
    
    return care_guide.get(wound_type.lower(), care_guide["cut"])


def check_infection_indicators(analysis: Dict) -> Tuple[bool, list]:
    """
    Check for infection indicators in wound analysis
    
    Returns:
        Tuple of (has_infection_signs, list_of_indicators)
    """
    indicators = []
    has_infection = False
    
    # Common infection signs
    infection_signs = {
        "redness": "Increased redness around wound",
        "swelling": "Swelling or puffiness",
        "warmth": "Warmth radiating from wound",
        "discharge": "Pus or unusual discharge",
        "odor": "Foul odor from wound",
        "lymphangitis": "Red streaking from wound"
    }
    
    # TODO: Parse actual vision API response for these indicators
    
    return has_infection, indicators