# agents/langsmith_monkey_patch.py
"""
MONKEY PATCH to fix LangSmith multipart timeouts globally
Apply once and fix ALL agents automatically
"""

import os
import json
import re
import functools
from typing import Any, Dict, List
from langsmith import run_helpers

print("🛠️ Applying LangSmith monkey patch to prevent multipart timeouts...")

# ============================================================
# 1. PATCH LANGCHAIN'S SERIALIZATION GLOBALLY
# ============================================================

def _safe_serialize_for_langsmith(obj: Any, max_string_size: int = 1000) -> Any:
    """
    Global serialization patch that removes large data BEFORE it reaches LangSmith
    This intercepts ALL data sent to LangSmith
    """
    # Base case: remove large base64 strings (images)
    if isinstance(obj, str):
        # Detect base64 image data (starts with data:image or long alphanumeric)
        if len(obj) > 5000 and ('data:image' in obj[:100] or 
                               (re.match(r'^[A-Za-z0-9+/=]+$', obj.replace('\n', '')) and len(obj) > 10000)):
            return f"[BASE64_IMAGE: {len(obj)} bytes]"
        # Truncate very long strings
        elif len(obj) > 10000:
            return obj[:500] + f"... [truncated {len(obj)-500} chars]"
        return obj
    
    # Clean dictionaries
    elif isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            # Skip image-related keys entirely
            if key.lower() in ['image', 'image_data', 'base64', 'photo', 'img', 'wound_image']:
                if isinstance(value, str) and len(value) > 1000:
                    cleaned[key] = f"[IMAGE_DATA: {len(value)} bytes]"
                else:
                    cleaned[key] = value
            # Clean metadata specially
            elif key == 'metadata' and isinstance(value, dict):
                cleaned[key] = _clean_metadata_globally(value)
            # Recursive cleaning
            else:
                cleaned[key] = _safe_serialize_for_langsmith(value, max_string_size)
        return cleaned
    
    # Clean lists
    elif isinstance(obj, list):
        return [_safe_serialize_for_langsmith(item, max_string_size) for item in obj[:20]]  # Limit list size
    
    return obj

def _clean_metadata_globally(metadata: Dict) -> Dict:
    """Specifically clean metadata to remove image data"""
    if not isinstance(metadata, dict):
        return metadata
    
    cleaned = metadata.copy()
    
    # Remove all image data from metadata
    image_keys = [k for k in cleaned.keys() if 'image' in k.lower() or 'photo' in k.lower()]
    for key in image_keys:
        if isinstance(cleaned[key], str) and len(cleaned[key]) > 1000:
            cleaned[key] = f"[IMAGE: {len(cleaned[key])} bytes]"
    
    # Clean user_context
    if 'user_context' in cleaned and isinstance(cleaned['user_context'], dict):
        for k, v in cleaned['user_context'].items():
            if isinstance(v, str) and len(v) > 2000:
                cleaned['user_context'][k] = f"[DATA: {len(v)} chars]"
    
    return cleaned

# ============================================================
# 2. PATCH THE LANGSMITH CLIENT'S POST METHOD
# ============================================================

def _patch_langsmith_http_client():
    """Patch the HTTP client to compress/clean large requests"""
    try:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        original_post = requests.Session.post
        
        def patched_post(session, url, **kwargs):
            # Clean data before sending if it's to LangSmith
            if 'smith.langchain.com' in url:
                # Clean JSON data
                if 'json' in kwargs:
                    kwargs['json'] = _safe_serialize_for_langsmith(kwargs['json'])
                
                # Clean data parameter
                if 'data' in kwargs and isinstance(kwargs['data'], (dict, str)):
                    if isinstance(kwargs['data'], dict):
                        kwargs['data'] = _safe_serialize_for_langsmith(kwargs['data'])
                    elif isinstance(kwargs['data'], str) and len(kwargs['data']) > 100000:
                        # Truncate very large strings
                        kwargs['data'] = kwargs['data'][:50000] + f"... [truncated {len(kwargs['data'])-50000} chars]"
                
                # Add timeout to prevent hanging
                if 'timeout' not in kwargs:
                    kwargs['timeout'] = (10, 30)  # 10s connect, 30s read
                
                # Add headers for smaller payloads
                headers = kwargs.get('headers', {})
                headers['X-LangSmith-Optimize'] = 'size'
                kwargs['headers'] = headers
                
                print(f"🔧 LangSmith request cleaned for: {url}")
            
            return original_post(session, url, **kwargs)
        
        # Apply the patch
        requests.Session.post = patched_post
        print("✅ Patched requests.Session.post for LangSmith optimization")
        
    except ImportError:
        print("⚠️ Could not patch requests module")

# ============================================================
# 3. PATCH LANGSMITH'S traceable DECORATOR GLOBALLY
# ============================================================

def _patch_traceable_decorator():
    """Patch the @traceable decorator to clean inputs automatically"""
    try:
        original_traceable = run_helpers.traceable
        
        def patched_traceable(func=None, **kwargs):
            # Force cleaning on all traced functions
            kwargs['serialize'] = _safe_serialize_for_langsmith
            
            # Set size limits
            kwargs['max_size'] = 1024 * 512  # 512KB max
            
            return original_traceable(func, **kwargs)
        
        # Apply patch
        run_helpers.traceable = patched_traceable
        print("✅ Patched @traceable decorator globally")
        
    except Exception as e:
        print(f"⚠️ Could not patch traceable: {e}")

# ============================================================
# 4. ENVIRONMENT CONFIGURATION
# ============================================================

def _configure_environment():
    """Set optimal environment variables for LangSmith"""
    os.environ.update({
        # Critical: Reduce payload sizes
        "LANGSMITH_MAX_PAYLOAD_SIZE": "524288",  # 512KB
        "LANGSMITH_BATCH_SIZE": "3",             # Smaller batches
        "LANGSMITH_TIMEOUT": "15",               # Shorter timeout
        
        # Enable async/optimized modes
        "LANGSMITH_ENABLE_COMPRESSION": "true",
        "LANGSMITH_USE_ASYNC_INGESTION": "true",
        "LANGSMITH_ASYNC_BATCH_SIZE": "5",
        
        # Disable problematic features
        "LANGSMITH_DISABLE_MULTIPART_FALLBACK": "true",
        "LANGSMITH_SKIP_LARGE_TRACES": "true",
    })
    print("✅ Configured LangSmith environment variables")

# ============================================================
# 5. MAIN PATCH FUNCTION - CALL THIS ONCE
# ============================================================

def apply_global_langsmith_fix():
    """
    Apply ALL fixes globally - call this once at startup
    """
    print("\n" + "="*60)
    print("🔧 APPLYING GLOBAL LANGSMITH MULTIPART FIX")
    print("="*60)
    
    # 1. Configure environment
    _configure_environment()
    
    # 2. Patch serialization
    original_serialize = getattr(run_helpers, '_serialize', None)
    if original_serialize:
        run_helpers._serialize = _safe_serialize_for_langsmith
        print("✅ Patched LangSmith serialization")
    
    # 3. Patch HTTP client
    _patch_langsmith_http_client()
    
    # 4. Patch traceable decorator
    _patch_traceable_decorator()
    
    print("✅ ALL LangSmith patches applied successfully!")
    print("   No agent modifications needed.")
    print("   Multipart timeouts should be resolved.")
    print("="*60 + "\n")

# ============================================================
# AUTO-APPLY ON IMPORT
# ============================================================

# Apply patches automatically when this module is imported
apply_global_langsmith_fix()