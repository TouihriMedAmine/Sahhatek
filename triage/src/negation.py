"""
Negation detection module using NegEx-style rule-based approach.

Detects if a symptom entity is negated based on negation indicators
appearing within a specified window before the entity.
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Negation indicators
NEGATION_INDICATORS: List[str] = [
    "no", "not", "without", "denies", "never", "free of", "absence of",
    "lack of", "negative for", "ruled out", "excluded"
]


def detect_negation(
    text: str,
    entity_start: int,
    entity_end: int,
    window_size: int = 3
) -> bool:
    """
    Detect if an entity is negated based on negation indicators.
    
    Args:
        text: The full text containing the entity
        entity_start: Character start position of the entity
        entity_end: Character end position of the entity
        window_size: Number of tokens to check before the entity (default: 3)
    
    Returns:
        True if the entity is negated, False otherwise
    """
    try:
        # Extract the text before the entity
        text_before = text[:entity_start].strip()
        
        if not text_before:
            return False
        
        # Tokenize the text before the entity (simple whitespace-based)
        tokens = text_before.lower().split()
        
        # Check the last window_size tokens for negation indicators
        check_tokens = tokens[-window_size:] if len(tokens) >= window_size else tokens
        
        # Check if any negation indicator appears in the tokens
        for token in check_tokens:
            # Remove punctuation for matching
            clean_token = token.strip('.,!?;:()[]{}"\'')
            if clean_token in NEGATION_INDICATORS:
                logger.debug(
                    f"Negation detected: '{clean_token}' found before entity "
                    f"at position {entity_start}-{entity_end}"
                )
                return True
        
        # Also check for multi-word negation indicators
        text_before_lower = text_before.lower()
        for indicator in NEGATION_INDICATORS:
            if len(indicator.split()) > 1:  # Multi-word indicator
                if indicator in text_before_lower:
                    # Check if it's within reasonable distance
                    indicator_pos = text_before_lower.rfind(indicator)
                    if indicator_pos != -1:
                        # Check if it's within the last 50 characters (rough heuristic)
                        if len(text_before) - indicator_pos < 50:
                            logger.debug(
                                f"Negation detected: '{indicator}' found before entity "
                                f"at position {entity_start}-{entity_end}"
                            )
                            return True
        
        return False
    
    except Exception as e:
        logger.error(f"Error detecting negation: {e}")
        return False


def detect_negation_with_spacy(
    doc,
    entity_start: int,
    entity_end: int,
    window_size: int = 3
) -> bool:
    """
    Detect negation using spaCy tokenization for more accurate results.
    
    Args:
        doc: spaCy Doc object
        entity_start: Character start position of the entity
        entity_end: Character end position of the entity
        window_size: Number of tokens to check before the entity (default: 3)
    
    Returns:
        True if the entity is negated, False otherwise
    """
    try:
        # Find the token that contains the entity start
        entity_token_idx = None
        for i, token in enumerate(doc):
            if token.idx <= entity_start < token.idx + len(token.text):
                entity_token_idx = i
                break
        
        if entity_token_idx is None or entity_token_idx == 0:
            return False
        
        # Check tokens before the entity
        start_idx = max(0, entity_token_idx - window_size)
        tokens_to_check = doc[start_idx:entity_token_idx]
        
        # Check if any token matches negation indicators
        for token in tokens_to_check:
            clean_text = token.text.lower().strip('.,!?;:()[]{}"\'')
            if clean_text in NEGATION_INDICATORS:
                logger.debug(
                    f"Negation detected (spaCy): '{clean_text}' found before entity "
                    f"at position {entity_start}-{entity_end}"
                )
                return True
        
        # Check for multi-word negation indicators in the span
        span_text = doc[start_idx:entity_token_idx].text.lower()
        for indicator in NEGATION_INDICATORS:
            if len(indicator.split()) > 1 and indicator in span_text:
                logger.debug(
                    f"Negation detected (spaCy): '{indicator}' found before entity "
                    f"at position {entity_start}-{entity_end}"
                )
                return True
        
        return False
    
    except Exception as e:
        logger.error(f"Error detecting negation with spaCy: {e}")
        # Fallback to simple method
        return detect_negation(doc.text, entity_start, entity_end, window_size)

