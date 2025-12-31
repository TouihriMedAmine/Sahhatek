# -*- coding: utf-8 -*-
"""
Text-to-Speech (TTS) service for Arabic using Edge TTS with multiple speakers
Edge TTS is free, supports Python 3.12, and has excellent Arabic voices
"""
import os
import base64
import asyncio
from typing import Optional, List


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
            if not self.arabic_voices:
                # Edge TTS Arabic voices (these are the actual voice names)
                self.arabic_voices = [
                    {"ShortName": "ar-TN-HediNeural", "Gender": "Male", "Locale": "ar-TN"},
                    {"ShortName": "ar-SA-HamedNeural", "Gender": "Male", "Locale": "ar-SA"},
                    {"ShortName": "ar-SA-ZariyahNeural", "Gender": "Female", "Locale": "ar-SA"},
                    {"ShortName": "ar-EG-SalmaNeural", "Gender": "Female", "Locale": "ar-EG"},
                    {"ShortName": "ar-EG-ShakirNeural", "Gender": "Male", "Locale": "ar-EG"},
                    {"ShortName": "ar-AE-FatimaNeural", "Gender": "Female", "Locale": "ar-AE"},
                    {"ShortName": "ar-AE-HamdanNeural", "Gender": "Male", "Locale": "ar-AE"},
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
                # Try to use ar-TN-HediNeural, but validate it exists
                preferred_voice = "ar-TN-HediNeural"
                # Check in all loaded voices (not just arabic_voices) since TN might not be filtered
                if self.voices:
                    for voice in self.voices:
                        if voice.get('ShortName', '') == preferred_voice:
                            print(f"✅ Found preferred voice: {preferred_voice}")
                            return preferred_voice
                    # If not found, use first available Arabic voice
                    if self.arabic_voices:
                        fallback = self.arabic_voices[0].get('ShortName', 'ar-SA-ZariyahNeural')
                        print(f"⚠️ Voice '{preferred_voice}' not found, using fallback: {fallback}")
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
            
            # Clean and normalize the text for TTS
            # Replace newlines with spaces (Edge TTS may stop at newlines)
            cleaned_text = text.replace('\n', ' ').replace('\r', ' ')
            # Remove extra whitespace but preserve single spaces
            cleaned_text = ' '.join(cleaned_text.split())
            
            # Normalize Unicode characters and clean text
            import unicodedata
            import re
            
            # Normalize Unicode (NFKC normalization helps with Arabic text)
            cleaned_text = unicodedata.normalize('NFKC', cleaned_text)
            
            # Remove any zero-width or control characters (except spaces and tabs)
            cleaned_text = ''.join(char for char in cleaned_text 
                                  if unicodedata.category(char)[0] != 'C' or char in ' \t')
            
            # Ensure proper spacing around punctuation (including Arabic punctuation)
            # Remove space before punctuation
            cleaned_text = re.sub(r'\s+([.,!?;:،؛])', r'\1', cleaned_text)
            # Ensure space after punctuation
            cleaned_text = re.sub(r'([.,!?;:،؛])(?!\s)', r'\1 ', cleaned_text)
            # Handle parentheses - ensure spaces around them
            cleaned_text = re.sub(r'\s*\(\s*', ' (', cleaned_text)
            cleaned_text = re.sub(r'\s*\)\s*', ') ', cleaned_text)
            
            # Final cleanup
            cleaned_text = cleaned_text.strip()
            
            # Remove any zero-width characters that might cause issues
            cleaned_text = ''.join(char for char in cleaned_text if unicodedata.category(char)[0] != 'C' or char in '\n\r\t')
            
            # Final cleanup - remove any remaining problematic characters
            cleaned_text = cleaned_text.strip()
            
            print(f"🔊 Synthesizing speech: {len(cleaned_text)} chars, voice: {voice_name}, language: {language}")
            print(f"🔊 Original text length: {len(text)} chars")
            print(f"🔊 Cleaned text: {cleaned_text}")
            
            # Synthesize speech asynchronously
            # Edge TTS can handle long texts, so we'll process the full text
            async def synthesize_async():
                from edge_tts.exceptions import NoAudioReceived
                try:
                    communicate = edge_tts.Communicate(cleaned_text, voice_name)
                    audio_data = b""
                    chunk_count = 0
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_data += chunk["data"]
                            chunk_count += 1
                        elif chunk["type"] == "metadata":
                            # Log metadata to debug
                            metadata = chunk.get('metadata', {})
                            if metadata:
                                print(f"🔊 TTS metadata: {metadata}")
                    print(f"🔊 Received {chunk_count} audio chunks, total size: {len(audio_data)} bytes")
                    return audio_data
                except NoAudioReceived as e:
                    # Voice doesn't exist or text has issues
                    print(f"⚠️ Voice '{voice_name}' failed: {e}")
                    print(f"⚠️ Text length: {len(cleaned_text)} chars")
                    print(f"⚠️ Text preview (repr): {repr(cleaned_text[:150])}")
                    
                    # Test if voice works with simple Arabic text
                    test_text = "مرحبا"
                    try:
                        print(f"🧪 Testing voice with simple text: {test_text}")
                        test_communicate = edge_tts.Communicate(test_text, voice_name)
                        test_audio = b""
                        async for chunk in test_communicate.stream():
                            if chunk["type"] == "audio":
                                test_audio += chunk["data"]
                        if test_audio:
                            print(f"✅ Voice works! Issue is with the input text. Trying more aggressive cleaning...")
                            # The problem is with the text - keep only safe characters
                            # Allow Arabic Unicode ranges, Latin, numbers, spaces, and basic punctuation
                            safe_text = ""
                            for char in cleaned_text:
                                code = ord(char)
                                # Arabic ranges
                                if (0x0600 <= code <= 0x06FF) or (0x0750 <= code <= 0x077F) or (0x08A0 <= code <= 0x08FF):
                                    safe_text += char
                                # Latin, numbers, spaces, basic punctuation
                                elif char.isalnum() or char in ' .,!?;:()[]{}':
                                    safe_text += char
                                # Keep Arabic punctuation
                                elif char in '،؛':
                                    safe_text += char
                            
                            safe_text = ' '.join(safe_text.split())
                            
                            if safe_text and safe_text != cleaned_text:
                                print(f"🔄 Retrying with safer text ({len(safe_text)} chars): {safe_text[:100]}...")
                                communicate = edge_tts.Communicate(safe_text, voice_name)
                                audio_data = b""
                                chunk_count = 0
                                async for chunk in communicate.stream():
                                    if chunk["type"] == "audio":
                                        audio_data += chunk["data"]
                                        chunk_count += 1
                                print(f"✅ Retry with safer text worked! Received {chunk_count} audio chunks")
                                return audio_data
                    except Exception as test_error:
                        print(f"⚠️ Voice test also failed: {test_error}")
                    
                    # If voice test fails or text cleaning didn't help, try fallback voices
                    print(f"🔄 Trying fallback voices...")
                    fallback_voices = ["ar-SA-ZariyahNeural", "ar-EG-SalmaNeural", "ar-DZ-AminaNeural", "ar-EG-ShakirNeural"]
                    for fallback_voice in fallback_voices:
                        try:
                            print(f"🔄 Trying fallback voice: {fallback_voice}")
                            communicate = edge_tts.Communicate(cleaned_text, fallback_voice)
                            audio_data = b""
                            chunk_count = 0
                            async for chunk in communicate.stream():
                                if chunk["type"] == "audio":
                                    audio_data += chunk["data"]
                                    chunk_count += 1
                            print(f"✅ Fallback voice '{fallback_voice}' worked! Received {chunk_count} audio chunks")
                            return audio_data
                        except Exception as fallback_error:
                            print(f"⚠️ Fallback voice {fallback_voice} also failed: {fallback_error}")
                            continue
                    # If all fallbacks fail, re-raise the original error
                    raise
            
            # Run async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio_data = loop.run_until_complete(synthesize_async())
            loop.close()
            
            if audio_data:
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
