"""
Symptom normalization module using fuzzy matching and synonym dictionary.

Normalizes symptom text spans to canonical symptom names using:
1. Exact matching
2. Fuzzy matching with RapidFuzz
3. Synonym dictionary lookup
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


class SymptomNormalizer:
    """Normalizes symptom text to canonical symptom names."""
    
    def __init__(self, symptom_dict_path: str, threshold: float = 75.0):
        """
        Initialize the normalizer with a symptom dictionary.
        
        Args:
            symptom_dict_path: Path to JSON file containing symptom dictionary
            threshold: Minimum fuzzy match score threshold (default: 75.0)
        """
        self.threshold = threshold
        self.symptom_dict: Dict[str, List[str]] = {}
        self._load_symptom_dict(symptom_dict_path)
    
    def _load_symptom_dict(self, path: str) -> None:
        """Load symptom dictionary from JSON file."""
        try:
            dict_path = Path(path)
            if not dict_path.exists():
                logger.warning(f"Symptom dictionary not found at {path}, using empty dict")
                self.symptom_dict = {}
                return
            
            with open(dict_path, 'r', encoding='utf-8') as f:
                self.symptom_dict = json.load(f)
            
            logger.info(f"Loaded {len(self.symptom_dict)} canonical symptoms from {path}")
        
        except Exception as e:
            logger.error(f"Error loading symptom dictionary: {e}")
            self.symptom_dict = {}
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text for matching.
        
        Args:
            text: Raw text to clean
        
        Returns:
            Cleaned lowercase text without punctuation
        """
        # Convert to lowercase
        text = text.lower().strip()
        
        # Remove punctuation (keep spaces)
        text = re.sub(r'[^\w\s]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _exact_match(self, cleaned_text: str) -> Optional[Tuple[str, float]]:
        """
        Check for exact match in symptom dictionary.
        
        Args:
            cleaned_text: Cleaned symptom text
        
        Returns:
            Tuple of (canonical symptom, score) if found, None otherwise
        """
        # Check direct match
        if cleaned_text in self.symptom_dict:
            return (cleaned_text, 100.0)
        
        # Check in synonym lists
        for canonical, synonyms in self.symptom_dict.items():
            if cleaned_text == canonical.lower() or cleaned_text in [s.lower() for s in synonyms]:
                return (canonical, 100.0)
        
        return None
    
    def _fuzzy_match(self, cleaned_text: str) -> Optional[Tuple[str, float]]:
        """
        Perform fuzzy matching against symptom dictionary.
        
        Args:
            cleaned_text: Cleaned symptom text
        
        Returns:
            Tuple of (canonical symptom, score) if match above threshold, None otherwise
        """
        best_match: Optional[str] = None
        best_score: float = 0.0
        
        # Check against canonical names
        for canonical in self.symptom_dict.keys():
            score = fuzz.token_sort_ratio(cleaned_text, canonical.lower())
            if score > best_score:
                best_score = score
                best_match = canonical
        
        # Check against synonyms
        for canonical, synonyms in self.symptom_dict.items():
            for synonym in synonyms:
                score = fuzz.token_sort_ratio(cleaned_text, synonym.lower())
                if score > best_score:
                    best_score = score
                    best_match = canonical
        
        # Return if above threshold
        if best_score >= self.threshold and best_match:
            return (best_match, best_score)
        
        return None
    
    def normalize(self, symptom_text: str) -> Optional[Dict[str, any]]:
        """
        Normalize a symptom text span to canonical form.
        
        Args:
            symptom_text: Raw symptom text span
        
        Returns:
            Dictionary with 'canonical' and 'score' keys if normalized,
            None if no match found above threshold
        """
        try:
            if not symptom_text or not symptom_text.strip():
                return None
            
            cleaned = self._clean_text(symptom_text)
            
            if not cleaned:
                return None
            
            # Try exact match first
            exact_result = self._exact_match(cleaned)
            if exact_result:
                canonical, score = exact_result
                logger.debug(f"Exact match: '{symptom_text}' -> '{canonical}'")
                return {
                    "canonical": canonical,
                    "score": score
                }
            
            # Try fuzzy match
            fuzzy_result = self._fuzzy_match(cleaned)
            if fuzzy_result:
                canonical, score = fuzzy_result
                logger.debug(f"Fuzzy match: '{symptom_text}' -> '{canonical}' (score: {score:.1f})")
                return {
                    "canonical": canonical,
                    "score": score
                }
            
            logger.debug(f"No match found for '{symptom_text}' (threshold: {self.threshold})")
            return None
        
        except Exception as e:
            logger.error(f"Error normalizing symptom '{symptom_text}': {e}")
            return None
    
    def add_symptom(self, canonical: str, synonyms: List[str]) -> None:
        """
        Add a new symptom to the dictionary.
        
        Args:
            canonical: Canonical symptom name
            synonyms: List of synonym variations
        """
        self.symptom_dict[canonical] = synonyms
        logger.info(f"Added symptom '{canonical}' with {len(synonyms)} synonyms")
    
    def get_all_canonicals(self) -> List[str]:
        """Get list of all canonical symptom names."""
        return list(self.symptom_dict.keys())

