# -*- coding: utf-8 -*-
"""
Real-time Arabic Transcription Service using Vosk
Based on the transcription_arabe_realtime.py implementation
"""
import os
import sounddevice as sd
import queue
import json
from vosk import Model, KaldiRecognizer
import arabic_reshaper
import time
from typing import Generator, Optional, Callable
import threading


# -----------------------
# CONFIG
# -----------------------
SAMPLE_RATE = 16000
BLOCKSIZE = 4000


class RealTimeTranscription:
    """
    Real-time transcription service using Vosk model for Arabic/Tunisian dialect.
    Supports both streaming transcription and batch processing.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the transcription service.
        
        Args:
            model_path: Path to Vosk model. If None, will search common locations.
        """
        self.model_path = model_path or self._find_model_path()
        self.model = None
        self.rec = None
        self.audio_q = queue.Queue()
        self.stream = None
        self.is_recording = False
        self._lock = threading.Lock()
        
        if self.model_path:
            self._load_model()
    
    def _find_model_path(self) -> Optional[str]:
        """Find Vosk model in common locations"""
        possible_paths = [
            "Modele_huhugging/vosk-model/vosk-model",
            os.path.join(os.path.dirname(__file__), "..", "..", "maaaheeeerrr", "Modele_huhugging", "vosk-model", "vosk-model"),
            "maaaheeeerrr/Modele_huhugging/vosk-model/vosk-model",
            os.path.join(os.path.dirname(__file__), "..", "..", "Modele_huhugging", "vosk-model", "vosk-model"),
        ]
        
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                print(f"✅ Found Vosk model at: {abs_path}")
                return abs_path
        
        print("⚠️ Vosk model not found. Please specify model_path.")
        return None
    
    def _load_model(self):
        """Load the Vosk model"""
        if not self.model_path or not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model path not found: {self.model_path}")
        
        print("🔁 Chargement du modèle...")
        try:
            self.model = Model(self.model_path)
            self.rec = KaldiRecognizer(self.model, SAMPLE_RATE)
            print("✅ Modèle chargé avec succès!")
        except Exception as e:
            print(f"❌ Erreur lors du chargement du modèle: {e}")
            raise
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream"""
        if status:
            print("⚠️ audio status:", status)
        self.audio_q.put(bytes(indata))
    
    def _start_stream(self):
        """Start audio input stream"""
        return sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCKSIZE,
            dtype='int16',
            channels=1,
            callback=self._audio_callback
        )
    
    @staticmethod
    def make_displayable(text: str) -> str:
        """
        Reshape Arabic text for proper display (connects Arabic letters).
        The browser handles RTL direction via CSS.
        We do NOT use get_display() to avoid double inversion.
        
        Args:
            text: Input text (may contain Arabic, French, English)
            
        Returns:
            Reshaped text with connected Arabic letters
        """
        if not text:
            return ""
        
        try:
            # Reshape only to connect Arabic letters
            # WITHOUT using get_display() which reverses order
            reshaped = arabic_reshaper.reshape(text)
            return reshaped
        except Exception as e:
            print(f"⚠️ Erreur dans make_displayable: {e}")
            return text
    
    def transcribe_generator(self) -> Generator[str, None, None]:
        """
        Generator that yields real-time transcription updates.
        
        Yields:
            str: Transcription text (reshaped for Arabic display)
        """
        if not self.model or not self.rec:
            raise RuntimeError("Model not loaded. Call _load_model() first.")
        
        with self._lock:
            if self.is_recording:
                raise RuntimeError("Already recording. Stop current recording first.")
            self.is_recording = True
        
        self.stream = self._start_stream()
        self.stream.start()
        buffer_total = ""
        last_yield = ""
        
        print("🎧 Micro en écoute... Parlez maintenant !")
        print("   (Appuyez sur 'Stop' dans Gradio pour arrêter)")
        
        try:
            while self.is_recording:
                try:
                    data = self.audio_q.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                if self.rec.AcceptWaveform(data):
                    # Final result of a segment
                    res = json.loads(self.rec.Result())
                    raw_text = res.get("text", "").strip()
                    
                    print(f"<< FINAL: {raw_text}")
                    
                    if raw_text:
                        # Add to buffer with space
                        if buffer_total:
                            buffer_total += " " + raw_text
                        else:
                            buffer_total = raw_text
                        
                        display = self.make_displayable(buffer_total)
                        
                        if display != last_yield:
                            last_yield = display
                            yield display
                else:
                    # Partial result (during speech)
                    pr = json.loads(self.rec.PartialResult())
                    partial = pr.get("partial", "").strip()
                    
                    if partial:
                        # Show buffer + temporary partial
                        combined = buffer_total + " " + partial if buffer_total else partial
                        display = self.make_displayable(combined.strip())
                        
                        if display != last_yield:
                            last_yield = display
                            yield display
                
                # Small delay to avoid CPU overload
                time.sleep(0.01)
        
        except GeneratorExit:
            print("✅ Transcription arrêtée.")
        finally:
            self._stop_recording()
    
    def _stop_recording(self):
        """Stop the audio stream"""
        with self._lock:
            self.is_recording = False
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except:
                    pass
                self.stream = None
    
    def stop(self):
        """Stop transcription (public method)"""
        self._stop_recording()
    
    def _convert_audio_to_pcm(self, audio_data: bytes, audio_format: str = "webm") -> bytes:
        """
        Convert audio from various formats (WebM, Opus, MP4) to PCM (16kHz, mono, int16).
        
        Args:
            audio_data: Audio bytes in any format
            audio_format: Format hint (webm, opus, mp4, wav)
            
        Returns:
            Raw PCM audio bytes (16kHz, mono, int16)
        """
        try:
            from pydub import AudioSegment
            import io
            
            # Create AudioSegment from bytes
            # Note: pydub requires ffmpeg for WebM/Opus support
            # Install with: pip install pydub (and ffmpeg separately)
            try:
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format=audio_format)
            except Exception as format_error:
                # Try without format hint (auto-detect)
                print(f"⚠️ Format-specific conversion failed, trying auto-detect: {format_error}")
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Convert to required format: 16kHz, mono, 16-bit
            audio_segment = audio_segment.set_frame_rate(SAMPLE_RATE)
            audio_segment = audio_segment.set_channels(1)  # Mono
            audio_segment = audio_segment.set_sample_width(2)  # 16-bit (2 bytes)
            
            # Export as raw PCM
            pcm_bytes = audio_segment.raw_data
            
            print(f"✅ Converted audio: {len(audio_data)} bytes -> {len(pcm_bytes)} bytes PCM")
            return pcm_bytes
            
        except ImportError:
            print("⚠️ pydub not installed. Install with: pip install pydub")
            print("   Also install ffmpeg for WebM/Opus support")
            # Fallback: assume it's already PCM or try to use it as-is
            return audio_data
        except Exception as e:
            print(f"⚠️ Audio conversion error: {e}")
            print(f"   Audio format: {audio_format}, Data size: {len(audio_data)} bytes")
            import traceback
            traceback.print_exc()
            # Try to use as-is - might already be PCM
            return audio_data
    
    def transcribe_audio_data(self, audio_data: bytes, audio_format: str = "webm") -> str:
        """
        Transcribe audio data (batch processing).
        
        Args:
            audio_data: Audio bytes (can be WebM, Opus, MP4, or raw PCM)
            audio_format: Format hint for conversion (webm, opus, mp4, wav)
            
        Returns:
            Transcribed text
        """
        if not self.model:
            self._load_model()
        
        if not self.rec:
            self.rec = KaldiRecognizer(self.model, SAMPLE_RATE)
        
        # Convert audio to PCM format if needed
        try:
            pcm_audio = self._convert_audio_to_pcm(audio_data, audio_format)
        except Exception as e:
            print(f"⚠️ Error converting audio: {e}")
            # Try using raw audio as-is
            pcm_audio = audio_data
        
        result_text = ""
        
        # Process audio in chunks
        chunk_size = BLOCKSIZE * 2  # 2 bytes per sample (int16)
        for i in range(0, len(pcm_audio), chunk_size):
            chunk = pcm_audio[i:i + chunk_size]
            
            if len(chunk) < chunk_size and i > 0:
                # Last chunk might be smaller, pad with zeros if needed
                chunk = chunk + b'\x00' * (chunk_size - len(chunk))
            
            if self.rec.AcceptWaveform(chunk):
                res = json.loads(self.rec.Result())
                text = res.get("text", "").strip()
                if text:
                    result_text += " " + text if result_text else text
        
        # Get final result
        try:
            final_res = json.loads(self.rec.FinalResult())
            final_text = final_res.get("text", "").strip()
            if final_text:
                result_text += " " + final_text if result_text else final_text
        except:
            pass
        
        return self.make_displayable(result_text.strip())


class TranscriptionService:
    """
    Singleton service wrapper for transcription.
    Provides easy access to transcription functionality.
    """
    _instance = None
    _transcription = None
    
    @classmethod
    def get_instance(cls, model_path: Optional[str] = None) -> RealTimeTranscription:
        """
        Get singleton transcription instance.
        
        Args:
            model_path: Optional model path (only used on first call)
            
        Returns:
            RealTimeTranscription instance
        """
        if cls._transcription is None:
            cls._transcription = RealTimeTranscription(model_path)
        return cls._transcription
    
    @classmethod
    def transcribe_audio(cls, audio_data: bytes, model_path: Optional[str] = None, audio_format: str = "webm") -> str:
        """
        Convenience method to transcribe audio data.
        
        Args:
            audio_data: Raw audio bytes (can be WebM, Opus, MP4, or raw PCM)
            model_path: Optional model path
            audio_format: Format hint for conversion (webm, opus, mp4, wav)
            
        Returns:
            Transcribed text
        """
        transcription = cls.get_instance(model_path)
        return transcription.transcribe_audio_data(audio_data, audio_format=audio_format)
    
    @classmethod
    def get_generator(cls, model_path: Optional[str] = None) -> Generator[str, None, None]:
        """
        Get transcription generator for real-time streaming.
        
        Args:
            model_path: Optional model path
            
        Returns:
            Generator yielding transcription updates
        """
        transcription = cls.get_instance(model_path)
        return transcription.transcribe_generator()


# -----------------------
# GRADIO INTERFACE
# -----------------------
def create_gradio_interface(model_path: Optional[str] = None):
    """
    Create Gradio interface for real-time transcription.
    
    Args:
        model_path: Optional path to Vosk model
        
    Returns:
        Gradio Blocks interface
    """
    try:
        import gradio as gr
    except ImportError:
        raise ImportError("Gradio is required. Install with: pip install gradio")
    
    transcription = RealTimeTranscription(model_path)
    
    def start_interface():
        with gr.Blocks(theme=gr.themes.Soft(), css="""
            .rtl-text textarea { 
                direction: rtl !important; 
                text-align: right !important;
                font-size: 20px !important;
                font-family: 'Traditional Arabic', 'Arial', 'Segoe UI', sans-serif !important;
                line-height: 2 !important;
                unicode-bidi: plaintext !important;
            }
        """) as demo:
            gr.Markdown("""
            # 🎙️ Transcription Arabe Tunisien en Temps Réel
            
            **Instructions:**
            1. Cliquez sur "Submit" pour démarrer
            2. Parlez en dialecte tunisien (avec des mots français si tu veux)
            3. La transcription s'affichera en temps réel avec les lettres arabes correctement connectées
            4. Cliquez sur "Stop" pour arrêter
            """)
            
            output_box = gr.Textbox(
                label="📝 Transcription",
                lines=10,
                interactive=False,
                elem_classes=["rtl-text"],
                placeholder="قاعد تسمع فيا توا... (La transcription apparaîtra ici)"
            )
            
            gr.Interface(
                fn=transcription.transcribe_generator,
                inputs=None,
                outputs=output_box,
                live=True,
                allow_flagging="never"
            )
            
            gr.Markdown("""
            ---
            💡 **Note:** 
            - Les lettres arabes sont automatiquement connectées
            - Les mots français/anglais restent lisibles
            - L'affichage est de droite à gauche (RTL)
            """)
        
        return demo
    
    return start_interface()


if __name__ == "__main__":
    # Standalone execution
    print("🎙️ Starting Real-time Arabic Transcription Service...")
    
    # Try to create interface
    try:
        interface_func = create_gradio_interface()
        demo = interface_func()
        demo.launch()
    except Exception as e:
        print(f"❌ Error starting interface: {e}")
        print("\n💡 You can also use this as a module:")
        print("   from agents.speech.transcription import TranscriptionService")
        print("   transcription = TranscriptionService.get_instance()")
        print("   for text in transcription.transcribe_generator():")
        print("       print(text)")

