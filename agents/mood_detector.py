# agents/mood_detector.py
import base64
import numpy as np
import cv2

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except Exception:
    DeepFace = None
    DEEPFACE_AVAILABLE = False


def decode_base64_image(data_url: str):
    """
    data_url format: "data:image/jpeg;base64,AAAA..."
    returns BGR image (OpenCV)
    """
    if not data_url:
        return None

    # remove prefix if exists
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]

    raw = base64.b64decode(data_url)
    np_arr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)  # BGR
    return img


def detect_mood_from_image_bgr(img_bgr):
    """
    Returns: dominant emotion string or "unknown"
    """
    if not DEEPFACE_AVAILABLE or img_bgr is None:
        return "unknown"

    try:
        result = DeepFace.analyze(
            img_path=img_bgr,
            actions=["emotion"],
            enforce_detection=False
        )
        if isinstance(result, list):
            result = result[0]
        return result.get("dominant_emotion", "unknown") or "unknown"
    except Exception:
        return "unknown"
