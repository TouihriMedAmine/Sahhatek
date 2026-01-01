# -*- coding: utf-8 -*-
"""
Translation service for English to Arabic using Groq LLM
"""
import os
from typing import Optional
import arabic_reshaper


class TranslationService:
    """
    Singleton service for English to Arabic translation using Groq LLM.
    Uses Groq API for high-quality translations.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TranslationService, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize Groq client (lazy loading)"""
        self.client = None
        self.client_loaded = False
        self.groq_api_key = os.getenv("GROQ_API_KEY", "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")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    def _load_client(self):
        """Lazy load the Groq client"""
        if self.client_loaded and self.client:
            return
        
        try:
            from groq import Groq
            
            if not self.groq_api_key:
                print("⚠️ GROQ_API_KEY not set. Translation will not work.")
                self.client_loaded = False
                return
            
            print("🔄 Initializing Groq client for translation...")
            self.client = Groq(api_key=self.groq_api_key)
            self.client_loaded = True
            print("✅ Groq client initialized for translation")
            
        except ImportError:
            print("⚠️ groq library not installed. Install with: pip install groq")
            self.client_loaded = False
        except Exception as e:
            print(f"❌ Error initializing Groq client: {e}")
            import traceback
            traceback.print_exc()
            self.client_loaded = False
    
    def translate(self, text: str, source_lang: str = "en", target_lang: str = "ar") -> str:
        """
        Translate text between English and Arabic using Groq LLM.
        
        Args:
            text: Text to translate
            source_lang: Source language code ("en" or "ar")
            target_lang: Target language code ("en" or "ar")
            
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return ""
        
        # Validate language pair
        if not ((source_lang == "en" and target_lang == "ar") or 
                (source_lang == "ar" and target_lang == "en")):
            print(f"⚠️ Translation from {source_lang} to {target_lang} not supported. Only en<->ar is supported.")
            return text
        
        # Load Groq client if needed
        self._load_client()
        
        if not self.client_loaded or not self.client:
            print("⚠️ Groq client not available. Returning original text.")
            return text
        
        try:
            # Build translation prompt
            if source_lang == "en" and target_lang == "ar":
                prompt = f"""Translate the following English text to Arabic. 
Provide only the Arabic translation, without any explanations or additional text.
Preserve the formatting, line breaks, and structure of the original text.

English text:
{text}

Arabic translation:"""
            else:  # Arabic to English
                prompt = f"""Translate the following Arabic text to English. 
Provide only the English translation, without any explanations or additional text.
Preserve the formatting, line breaks, and structure of the original text.

Arabic text:
{text}

English translation:"""
            
            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.groq_model,
                messages=[
                    {"role": "system", "content": "You are a professional translator. Translate accurately and preserve the original formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent translations
                max_tokens=2000  # Allow for longer translations
            )
            
            translated_text = response.choices[0].message.content.strip()
            
            # Reshape Arabic text for proper display (only if target is Arabic)
            if target_lang == "ar":
                translated_text = self._reshape_arabic(translated_text)
            
            return translated_text.strip()
            
        except Exception as e:
            print(f"❌ Translation error: {e}")
            import traceback
            traceback.print_exc()
            return text
    
    def _reshape_arabic(self, text: str) -> str:
        """
        Reshape Arabic text for proper display (connect letters).
        Similar to the transcription service.
        """
        if not text:
            return ""
        
        try:
            # Reshape Arabic letters for proper connection
            reshaped = arabic_reshaper.reshape(text)
            return reshaped
        except Exception as e:
            print(f"⚠️ Arabic reshaping error: {e}")
            return text
    
    def is_available(self) -> bool:
        """Check if translation service is available"""
        if not self.client_loaded:
            self._load_client()
        return self.client_loaded and self.client is not None
