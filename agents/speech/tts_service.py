# -*- coding: utf-8 -*-
"""
Text-to-Speech (TTS) service for Arabic using Edge TTS with multiple speakers
Edge TTS is free, supports Python 3.12, and has excellent Arabic voices
"""
import os
import base64
import asyncio
import hashlib
from typing import Optional, List
from functools import lru_cache


class TTSService:
    """
    Singleton service for Arabic Text-to-Speech using Edge TTS.
    Supports multiple speaker voices.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TTSService, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize TTS service (lazy loading)"""
        self.voices_loaded = False
        self.voices = []  # All voices from Edge TTS
        self.arabic_voices = []  # Filtered Arabic voices
        self.speakers = []  # Friendly names for UI
        self.current_speaker = None
        self._audio_cache = {}  # Cache for generated audio (text_hash -> audio_data)
        self._cache_max_size = 100  # Maximum cache entries
        
    def _load_voices(self):
        """Lazy load available voices"""
        if self.voices_loaded:
            return
        
        try:
            import edge_tts
            
            print("🔄 Loading Edge TTS voices...")
            
            # Get all available voices asynchronously
            async def get_voices():
                voices = await edge_tts.list_voices()
                return voices
            
            # Run async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            all_voices = loop.run_until_complete(get_voices())
            loop.close()
            
            # Store all voices first for validation
            self.voices = all_voices
            
            # Filter Arabic voices
            self.arabic_voices = [
                v for v in all_voices 
                if 'ar' in v.get('Locale', '').lower() or 'Arabic' in v.get('Locale', '')
            ]
            
            # If no Arabic voices found, use common Arabic voice names
            # NOTE: Higher quality voices are listed first (based on user feedback and quality)
            if not self.arabic_voices:
                # Edge TTS Arabic voices (these are the actual voice names)
                # Best quality voices (recommended):
                # - ar-SA-ZariyahNeural: High-quality female Saudi voice (most natural)
                # - ar-EG-SalmaNeural: High-quality female Egyptian voice (clear pronunciation)
                # - ar-TN-HediNeural: High-quality male Tunisian voice (natural intonation)
                self.arabic_voices = [
                    {"ShortName": "ar-SA-ZariyahNeural", "Gender": "Female", "Locale": "ar-SA", "Quality": "High"},
                    {"ShortName": "ar-EG-SalmaNeural", "Gender": "Female", "Locale": "ar-EG", "Quality": "High"},
                    {"ShortName": "ar-TN-HediNeural", "Gender": "Male", "Locale": "ar-TN", "Quality": "High"},
                    {"ShortName": "ar-EG-ShakirNeural", "Gender": "Male", "Locale": "ar-EG", "Quality": "High"},
                    {"ShortName": "ar-SA-HamedNeural", "Gender": "Male", "Locale": "ar-SA", "Quality": "Medium"},
                    {"ShortName": "ar-AE-FatimaNeural", "Gender": "Female", "Locale": "ar-AE", "Quality": "Medium"},
                    {"ShortName": "ar-AE-HamdanNeural", "Gender": "Male", "Locale": "ar-AE", "Quality": "Medium"},
                    # Additional high-quality voices (if available)
                    {"ShortName": "ar-DZ-AminaNeural", "Gender": "Female", "Locale": "ar-DZ", "Quality": "High"},
                    {"ShortName": "ar-MA-MounaNeural", "Gender": "Female", "Locale": "ar-MA", "Quality": "High"},
                ]
            
            # Create speaker list with friendly names
            self.speakers = []
            for voice in self.arabic_voices:
                name = voice.get('ShortName', '')
                gender = voice.get('Gender', 'Unknown')
                locale = voice.get('Locale', '')
                friendly_name = f"{name} ({gender})"
                self.speakers.append(friendly_name)
            
            # Also add English voices for English text
            english_voices = [
                v for v in all_voices 
                if 'en' in v.get('Locale', '').lower() and 'US' in v.get('Locale', '')
            ]
            for voice in english_voices[:3]:  # Add first 3 English voices
                name = voice.get('ShortName', '')
                gender = voice.get('Gender', 'Unknown')
                friendly_name = f"{name} ({gender})"
                self.speakers.append(friendly_name)
            
            # Set default speaker (first Arabic female voice)
            if self.arabic_voices:
                self.current_speaker = self.speakers[0]
            
            self.voices_loaded = True
            print(f"✅ Edge TTS voices loaded. Available speakers: {len(self.speakers)}")
            for i, speaker in enumerate(self.speakers[:10]):  # Show first 10
                print(f"   {i+1}. {speaker}")
            if len(self.speakers) > 10:
                print(f"   ... and {len(self.speakers) - 10} more")
            
        except ImportError:
            print("⚠️ edge-tts library not installed. Install with: pip install edge-tts")
            self.voices_loaded = False
        except Exception as e:
            print(f"❌ Error loading Edge TTS voices: {e}")
            import traceback
            traceback.print_exc()
            self.voices_loaded = False
    
    def _get_voice_name(self, speaker: Optional[str] = None, language: str = "ar") -> str:
        """Get voice name from speaker friendly name"""
        # If no speaker provided, use default based on language
        if not speaker:
            if language == "ar":
                # Use best quality female voice as default (ar-SA-ZariyahNeural is highly rated)
                # This voice has excellent pronunciation and natural intonation for medical/health content
                preferred_voice = "ar-SA-ZariyahNeural"
                # Check in all loaded voices (not just arabic_voices) since SA might not be filtered
                if self.voices:
                    for voice in self.voices:
                        if voice.get('ShortName', '') == preferred_voice:
                            print(f"✅ Found preferred voice: {preferred_voice}")
                            return preferred_voice
                    # If not found, try other high-quality voices
                    high_quality_fallbacks = ["ar-EG-SalmaNeural", "ar-TN-HediNeural", "ar-EG-ShakirNeural"]
                    for fallback_voice in high_quality_fallbacks:
                        for voice in self.voices:
                            if voice.get('ShortName', '') == fallback_voice:
                                print(f"✅ Using high-quality fallback: {fallback_voice}")
                                return fallback_voice
                    # If still not found, use first available Arabic voice
                    if self.arabic_voices:
                        fallback = self.arabic_voices[0].get('ShortName', 'ar-SA-ZariyahNeural')
                        print(f"⚠️ Preferred voices not found, using fallback: {fallback}")
                        return fallback
                    else:
                        return "ar-SA-ZariyahNeural"  # Hardcoded fallback
                else:
                    # Voices not loaded yet, return preferred (will be validated by Edge TTS with fallback)
                    return preferred_voice
            else:
                return "en-US-AriaNeural"  # Default English voice
        
        # Extract voice name from friendly name (format: "ar-SA-ZariyahNeural (Female)")
        if "(" in speaker:
            voice_name = speaker.split("(")[0].strip()
        else:
            voice_name = speaker
        
        # Validate voice name - if it's not a valid Edge TTS voice, use default
        # Check if it matches any of our loaded voices
        valid_voice = False
        for voice in self.arabic_voices + self.voices:
            if voice.get('ShortName', '') == voice_name:
                valid_voice = True
                break
        
        if not valid_voice:
            # Invalid voice name, use default
            print(f"⚠️ Invalid voice '{voice_name}', using default for language {language}")
            if language == "ar":
                return "ar-TN-HediNeural"
            else:
                return "en-US-AriaNeural"
        
        return voice_name
    
    def synthesize(self, text: str, speaker: Optional[str] = None, language: str = "ar") -> Optional[bytes]:
        """
        Synthesize speech from text using Edge TTS.
        
        Args:
            text: Text to convert to speech
            speaker: Speaker voice name (optional, uses default if not provided)
            language: Language code (default: "ar" for Arabic)
            
        Returns:
            Audio data as bytes (MP3 format) or None if error
        """
        if not text or not text.strip():
            return None
        
        # Load voices if needed
        self._load_voices()
        
        if not self.voices_loaded:
            print("⚠️ Edge TTS voices not available.")
            return None
        
        try:
            import edge_tts
            
            # Get voice name
            voice_name = self._get_voice_name(speaker, language)
            
            # Check cache first (for repeated text)
            cache_key = hashlib.md5(f"{text}_{voice_name}_{language}".encode('utf-8')).hexdigest()
            if cache_key in self._audio_cache:
                print(f"✅ Using cached audio for text (length: {len(text)} chars)")
                return self._audio_cache[cache_key]
            
            # Clean and normalize the text for TTS (optimized - only essential cleaning)
            # Replace newlines with spaces (Edge TTS may stop at newlines)
            cleaned_text = text.replace('\n', ' ').replace('\r', ' ')
            # Remove extra whitespace but preserve single spaces
            cleaned_text = ' '.join(cleaned_text.split())
            
            # Normalize Unicode characters (essential for Arabic)
            import unicodedata
            cleaned_text = unicodedata.normalize('NFKC', cleaned_text)
            
            # Remove control characters (except spaces)
            cleaned_text = ''.join(char for char in cleaned_text 
                                  if unicodedata.category(char)[0] != 'C' or char in ' \t')
            
            # Final cleanup
            cleaned_text = cleaned_text.strip()
            
            # Limit text length for faster processing (split very long texts)
            MAX_TEXT_LENGTH = 5000  # Edge TTS can handle this, but shorter is faster
            if len(cleaned_text) > MAX_TEXT_LENGTH:
                print(f"⚠️ Text is very long ({len(cleaned_text)} chars), truncating to {MAX_TEXT_LENGTH} for faster processing")
                cleaned_text = cleaned_text[:MAX_TEXT_LENGTH] + "..."
            
            print(f"🔊 Synthesizing speech: {len(cleaned_text)} chars, voice: {voice_name}, language: {language}")
            
            # Synthesize speech asynchronously (optimized - direct call, no complex fallbacks)
            async def synthesize_async():
                from edge_tts.exceptions import NoAudioReceived
                try:
                    # Direct synthesis with timeout handling
                    communicate = edge_tts.Communicate(cleaned_text, voice_name)
                    audio_data = b""
                    chunk_count = 0
                    
                    # Stream audio chunks (this is async, so it's non-blocking)
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_data += chunk["data"]
                            chunk_count += 1
                    
                    print(f"🔊 Received {chunk_count} audio chunks, total size: {len(audio_data)} bytes")
                    return audio_data
                except NoAudioReceived as e:
                    # Voice doesn't exist or text has issues - try one fallback only (faster)
                    print(f"⚠️ Voice '{voice_name}' failed: {e}")
                    # Try one high-quality fallback (ar-SA-ZariyahNeural is most reliable)
                    if voice_name != "ar-SA-ZariyahNeural":
                        try:
                            print(f"🔄 Trying fallback voice: ar-SA-ZariyahNeural")
                            communicate = edge_tts.Communicate(cleaned_text, "ar-SA-ZariyahNeural")
                            audio_data = b""
                            chunk_count = 0
                            async for chunk in communicate.stream():
                                if chunk["type"] == "audio":
                                    audio_data += chunk["data"]
                                    chunk_count += 1
                            print(f"✅ Fallback voice worked! Received {chunk_count} audio chunks")
                            return audio_data
                        except Exception as fallback_error:
                            print(f"⚠️ Fallback voice also failed: {fallback_error}")
                    # If fallback fails, re-raise the original error
                    raise
            
            # Run async function (optimized - reuse event loop if possible)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            audio_data = loop.run_until_complete(synthesize_async())
            
            if audio_data:
                # Cache the result (limit cache size to prevent memory issues)
                if len(self._audio_cache) >= self._cache_max_size:
                    # Remove oldest entry (simple FIFO)
                    oldest_key = next(iter(self._audio_cache))
                    del self._audio_cache[oldest_key]
                self._audio_cache[cache_key] = audio_data
                
                # Edge TTS returns MP3 by default
                return audio_data
            else:
                print("⚠️ No audio data generated")
                return None
            
        except ImportError:
            print("⚠️ edge-tts library not installed. Install with: pip install edge-tts")
            return None
        except Exception as e:
            print(f"❌ TTS synthesis error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def synthesize_to_base64(self, text: str, speaker: Optional[str] = None, language: str = "ar") -> Optional[str]:
        """
        Synthesize speech and return as base64-encoded string.
        
        Args:
            text: Text to convert to speech
            speaker: Speaker voice name (optional)
            language: Language code (default: "ar")
            
        Returns:
            Base64-encoded audio data or None if error
        """
        audio_data = self.synthesize(text, speaker=speaker, language=language)
        if audio_data:
            return base64.b64encode(audio_data).decode('utf-8')
        return None
    
    def get_speakers(self) -> List[str]:
        """Get list of available speakers"""
        self._load_voices()
        return self.speakers.copy() if self.speakers else []
    
    def set_speaker(self, speaker: str) -> bool:
        """Set the default speaker"""
        self._load_voices()
        if speaker in self.speakers:
            self.current_speaker = speaker
            return True
        return False
    
    def is_available(self) -> bool:
        """Check if TTS service is available"""
        if not self.voices_loaded:
            self._load_voices()
        return self.voices_loaded


# Convenience function
def synthesize_speech(text: str, speaker: Optional[str] = None, language: str = "ar") -> Optional[bytes]:
    """Convenience function to synthesize speech"""
    service = TTSService.get_instance()
    return service.synthesize(text, speaker=speaker, language=language)
