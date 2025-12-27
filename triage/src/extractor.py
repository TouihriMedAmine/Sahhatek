"""
Main symptom extraction pipeline.

Combines NER, normalization, and negation detection to extract
and normalize symptoms from free-text patient prompts.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import spacy

try:
    from .negation import detect_negation_with_spacy
    from .normalize import SymptomNormalizer
except ImportError:
    # Fallback/Legacy
    from src.negation import detect_negation_with_spacy
    from src.normalize import SymptomNormalizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Common false positive words to filter out
FALSE_POSITIVE_WORDS = {
    "me", "i", "you", "he", "she", "it", "we", "they", "them", "us",
    "my", "your", "his", "her", "its", "our", "their",
    "this", "that", "these", "those",
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "be", "been", "being", "am", "are", "is",
    "feel", "feeling", "very", "really", "quite", "too", "so", "much",
    "more", "most", "less", "least", "some", "any", "all", "both"
}

# Phrases that are definitely not symptoms
FALSE_POSITIVE_PHRASES = {
    "feel very", "feel really", "feel quite", "feel so", "feel too",
    "very", "really", "quite", "too", "so much", "feel", "feeling",
    "i feel", "i'm feeling", "i am feeling"
}


class SymptomExtractor:
    """Main symptom extraction pipeline."""
    
    def __init__(
        self,
        model_path: str = "models/symptom_ner_spacy",
        symptom_dict_path: str = "data/symptom_dict.json",
        normalization_threshold: float = 75.0
    ):
        """
        Initialize the symptom extractor.
        
        Args:
            model_path: Path to trained spaCy NER model
            symptom_dict_path: Path to symptom dictionary JSON file
            normalization_threshold: Minimum fuzzy match score threshold
        """
        self.model_path = model_path
        self.nlp: Optional[spacy.Language] = None
        self.normalizer: Optional[SymptomNormalizer] = None
        
        self._load_model()
        self._load_normalizer(symptom_dict_path, normalization_threshold)
    
    def _load_model(self) -> None:
        """Load the trained spaCy NER model."""
        try:
            model_path = Path(self.model_path)
            if not model_path.exists():
                logger.warning(
                    f"Model not found at {self.model_path}. "
                    "Please train the model first using train_ner.py"
                )
                # Fallback to blank model
                self.nlp = spacy.blank("en")
                if "ner" not in self.nlp.pipe_names:
                    self.nlp.add_pipe("ner")
                logger.warning("Using blank model - results may be poor")
                return
            
            self.nlp = spacy.load(self.model_path)
            logger.info(f"Loaded NER model from {self.model_path}")
        
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            # Fallback to blank model
            self.nlp = spacy.blank("en")
            if "ner" not in self.nlp.pipe_names:
                self.nlp.add_pipe("ner")
            logger.warning("Using blank model due to error")
    
    def _load_normalizer(self, dict_path: str, threshold: float) -> None:
        """Load the symptom normalizer."""
        try:
            self.normalizer = SymptomNormalizer(dict_path, threshold)
            logger.info("Symptom normalizer loaded")
        except Exception as e:
            logger.error(f"Error loading normalizer: {e}")
            raise
    
    def _is_false_positive(self, symptom_text: str, doc, ent_start: int, ent_end: int) -> bool:
        """
        Check if an extracted entity is likely a false positive.
        
        Args:
            symptom_text: The extracted symptom text
            doc: spaCy doc object
            ent_start: Entity start character position
            ent_end: Entity end character position
        
        Returns:
            True if likely a false positive, False otherwise
        """
        # Filter very short entities (less than 3 characters)
        if len(symptom_text.strip()) < 3:
            logger.debug(f"Filtering short entity: '{symptom_text}'")
            return True
        
        # Filter phrases that are definitely not symptoms
        symptom_lower = symptom_text.lower().strip()
        if symptom_lower in FALSE_POSITIVE_PHRASES:
            logger.debug(f"Filtering false positive phrase: '{symptom_text}'")
            return True
        
        # Check if it starts with false positive phrases
        for phrase in FALSE_POSITIVE_PHRASES:
            if symptom_lower.startswith(phrase + " ") or symptom_lower == phrase:
                logger.debug(f"Filtering phrase starting with false positive: '{symptom_text}'")
                return True
        
        # Remove punctuation for checking
        symptom_clean = re.sub(r'[^\w\s]', '', symptom_lower)
        
        # Filter single words that are common false positives
        if symptom_clean in FALSE_POSITIVE_WORDS:
            logger.debug(f"Filtering false positive word: '{symptom_text}'")
            return True
        
        # Filter if it's just "feel" or "very" or similar
        words = symptom_clean.split()
        if len(words) <= 2 and all(word in FALSE_POSITIVE_WORDS for word in words):
            logger.debug(f"Filtering phrase with only false positive words: '{symptom_text}'")
            return True
        
        # Filter if it's a single token and it's a pronoun/determiner
        try:
            # Get tokens in the entity span
            entity_tokens = [token for token in doc if ent_start <= token.idx < ent_end]
            if len(entity_tokens) == 1:
                token = entity_tokens[0]
                # Check if it's a pronoun, determiner, or other non-content word
                if token.pos_ in ["PRON", "DET", "AUX", "PART"]:
                    logger.debug(f"Filtering non-content word: '{symptom_text}' (POS: {token.pos_})")
                    return True
        except Exception:
            pass
        
        # Filter entities that are just punctuation, numbers, or whitespace
        # Remove all whitespace and check if only punctuation/numbers remain
        text_no_ws = re.sub(r'\s+', '', symptom_text)
        if text_no_ws and re.match(r'^[\d\.,!?;:()\[\]{}"\'-]+$', text_no_ws):
            logger.debug(f"Filtering punctuation/number entity: '{symptom_text}'")
            return True
        
        # Filter single punctuation characters
        if len(symptom_text.strip()) == 1 and symptom_text.strip() in '.,!?;:()[]{}"\'-':
            logger.debug(f"Filtering single punctuation: '{symptom_text}'")
            return True
        
        return False
    
    def extract(self, text: str) -> Dict[str, List[Dict[str, any]]]:
        """
        Extract and normalize symptoms from text.
        
        Args:
            text: Input text to process
        
        Returns:
            Dictionary with 'symptoms' key containing list of extracted symptoms
        """
        if not text or not text.strip():
            return {"symptoms": []}
        
        try:
            # Process text with spaCy
            doc = self.nlp(text)
            
            # Extract symptom entities
            extracted_symptoms = []
            seen_canonicals = set()  # For deduplication
            
            for ent in doc.ents:
                if ent.label_ == "SYMPTOM":
                    symptom_text = ent.text.strip()
                    
                    # Filter false positives
                    if self._is_false_positive(symptom_text, doc, ent.start_char, ent.end_char):
                        logger.debug(f"Filtering false positive: '{symptom_text}'")
                        continue
                    
                    # Detect negation
                    is_negated = detect_negation_with_spacy(
                        doc,
                        ent.start_char,
                        ent.end_char,
                        window_size=3
                    )
                    
                    # Skip negated symptoms
                    if is_negated:
                        logger.debug(f"Skipping negated symptom: '{symptom_text}'")
                        continue
                    
                    # Normalize symptom
                    normalization_result = self.normalizer.normalize(symptom_text)
                    
                    if normalization_result:
                        canonical = normalization_result["canonical"]
                        score = normalization_result["score"]
                        
                        # Deduplicate by canonical name
                        if canonical not in seen_canonicals:
                            seen_canonicals.add(canonical)
                            
                            extracted_symptoms.append({
                                "text": symptom_text,
                                "canonical": canonical,
                                "score": round(score, 1),
                                "negated": False,
                                "start": ent.start_char,
                                "end": ent.end_char
                            })
                        else:
                            logger.debug(
                                f"Skipping duplicate canonical symptom: '{canonical}'"
                            )
                    else:
                        # Include even if normalization failed (with lower confidence)
                        logger.debug(
                            f"Could not normalize '{symptom_text}', "
                            "including with low confidence"
                        )
                        extracted_symptoms.append({
                            "text": symptom_text,
                            "canonical": symptom_text.lower(),
                            "score": 50.0,  # Low confidence for unnormalized
                            "negated": False,
                            "start": ent.start_char,
                            "end": ent.end_char
                        })
            
            logger.info(f"Extracted {len(extracted_symptoms)} symptoms from text")
            
            return {
                "symptoms": extracted_symptoms
            }
        
        except Exception as e:
            logger.error(f"Error extracting symptoms: {e}")
            return {"symptoms": []}
    
    def extract_simple(self, text: str) -> List[Dict[str, any]]:
        """
        Extract symptoms and return simplified format (without offsets).
        
        Args:
            text: Input text to process
        
        Returns:
            List of symptom dictionaries without start/end offsets
        """
        result = self.extract(text)
        symptoms = result.get("symptoms", [])
        
        # Remove start/end fields for simplified output
        simplified = []
        for symptom in symptoms:
            simplified.append({
                "text": symptom["text"],
                "canonical": symptom["canonical"],
                "score": symptom["score"],
                "negated": symptom["negated"]
            })
        
        return simplified


def main():
    """Test the extractor."""
    # CONFIG
    TEST_TEXT = "my throat burns and I'm coughing but no fever"
    
    logger.info("Initializing symptom extractor...")
    extractor = SymptomExtractor()
    
    logger.info(f"\nProcessing text: '{TEST_TEXT}'")
    result = extractor.extract(TEST_TEXT)
    
    print("\nExtracted Symptoms:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

