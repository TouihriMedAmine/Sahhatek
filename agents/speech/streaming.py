# -*- coding: utf-8 -*-
"""
Streaming audio transcription for real-time processing
"""
import json
import base64
from typing import Generator, Optional
from vosk import KaldiRecognizer
# Import constants
SAMPLE_RATE = 16000
BLOCKSIZE = 4000


class StreamingTranscriber:
    """
    Handles streaming audio transcription for real-time processing.
    Processes audio chunks as they arrive and returns partial results.
    
    Buffers WebM chunks and converts them in batches (since small WebM chunks
    are incomplete files that FFmpeg can't parse).
    """
    
    def __init__(self, model):
        """
        Initialize with a loaded Vosk model.
        
        Args:
            model: Loaded Vosk Model instance
        """
        self.model = model
        self.rec = KaldiRecognizer(model, SAMPLE_RATE)
        self.buffer_total = ""
        self.last_partial = ""
        # Buffer for accumulating WebM chunks before conversion
        self.webm_buffer = []
        self.min_buffer_size = 50000  # ~1-2 seconds of audio (50KB)
    
    def process_webm_chunk(self, audio_chunk_webm: bytes, audio_format: str = "webm", is_final: bool = False) -> dict:
        """
        Process a WebM audio chunk. Buffers chunks and converts in batches.
        
        Args:
            audio_chunk_webm: WebM/Opus audio bytes
            audio_format: Format hint (webm, opus)
            is_final: Whether this is the final chunk
            
        Returns:
            dict with transcription results
        """
        # Add chunk to buffer
        if audio_chunk_webm and len(audio_chunk_webm) > 0:
            self.webm_buffer.append(audio_chunk_webm)
        
        # Convert buffer if we have enough data OR if it's the final chunk
        total_buffer_size = sum(len(chunk) for chunk in self.webm_buffer)
        should_process = is_final or total_buffer_size >= self.min_buffer_size
        
        if not should_process and len(self.webm_buffer) > 0:
            # Not enough data yet, return current state (keep existing transcription)
            print(f"⏸️ Buffering chunk {len(self.webm_buffer)} ({total_buffer_size} bytes, need {self.min_buffer_size})")
            return {
                "text": "",
                "partial": "",
                "is_final": False,
                "full_text": self.buffer_total
            }
        
        # Convert accumulated buffer to PCM
        if len(self.webm_buffer) > 0:
            combined_webm = b''.join(self.webm_buffer)
            print(f"🔄 Converting buffered audio: {len(self.webm_buffer)} chunks, {total_buffer_size} bytes total")
            pcm_data = convert_audio_chunk_to_pcm(combined_webm, audio_format)
            self.webm_buffer = []  # Clear buffer after conversion
            
            if pcm_data and len(pcm_data) > 0:
                return self.process_chunk(pcm_data, is_final=is_final)
            else:
                print("⚠️ Failed to convert buffered audio")
        
        # Return current state if no processing happened
        return {
            "text": "",
            "partial": "",
            "is_final": is_final,
            "full_text": self.buffer_total
        }
    
    def process_chunk(self, audio_chunk_pcm: bytes, is_final: bool = False) -> dict:
        """
        Process a single audio chunk and return transcription result.
        
        Args:
            audio_chunk_pcm: Raw PCM audio bytes (16kHz, mono, int16)
            is_final: Whether this is the final chunk
            
        Returns:
            dict with keys:
                - text: Final transcription text (if available)
                - partial: Partial transcription (during speech)
                - is_final: Whether this is a final result
                - full_text: Combined buffer + current result
        """
        result = {
            "text": "",
            "partial": "",
            "is_final": False,
            "full_text": self.buffer_total
        }
        
        if not audio_chunk_pcm or len(audio_chunk_pcm) == 0:
            print("⚠️ Empty PCM chunk, skipping")
            return result
        
        # Process chunk with Vosk (matching reference code lines 82-113)
        if self.rec.AcceptWaveform(audio_chunk_pcm):
            # Final result of a segment (reference code lines 82-100)
            res = json.loads(self.rec.Result())
            raw_text = res.get("text", "").strip()
            
            if raw_text:
                print(f"✅ FINAL result: '{raw_text}'")
                # Add to buffer with space (matching reference code lines 91-94)
                if self.buffer_total:
                    self.buffer_total += " " + raw_text
                else:
                    self.buffer_total = raw_text
                
                result["text"] = raw_text
                result["is_final"] = True
                result["full_text"] = self.buffer_total
                self.last_partial = ""  # Clear partial on final
        else:
            # Partial result (during speech) - reference code lines 102-113
            pr = json.loads(self.rec.PartialResult())
            partial = pr.get("partial", "").strip()
            
            if partial:
                # Combine buffer + partial for real-time display (matching reference code line 108)
                combined = (self.buffer_total + " " + partial).strip() if self.buffer_total else partial
                result["partial"] = partial
                result["full_text"] = combined  # This is what gets displayed in real-time
                self.last_partial = partial
                print(f"🔄 PARTIAL result: '{partial}' -> full_text: '{combined}'")
            else:
                # No partial yet, but keep existing buffer
                result["full_text"] = self.buffer_total
                if self.buffer_total:
                    print(f"⏸️ No partial yet, keeping buffer: '{self.buffer_total}'")
        
        # If final chunk, get any remaining final result
        if is_final:
            try:
                final_res = json.loads(self.rec.FinalResult())
                final_text = final_res.get("text", "").strip()
                if final_text:
                    if self.buffer_total:
                        self.buffer_total += " " + final_text
                    else:
                        self.buffer_total = final_text
                    result["text"] = final_text
                    result["is_final"] = True
                    result["full_text"] = self.buffer_total
            except:
                pass
        
        return result
    
    def reset(self):
        """Reset the transcriber state for a new session"""
        self.rec = KaldiRecognizer(self.model, SAMPLE_RATE)
        self.buffer_total = ""
        self.last_partial = ""
        self.webm_buffer = []


def convert_audio_chunk_to_pcm(audio_chunk: bytes, audio_format: str = "webm") -> bytes:
    """
    Convert a single audio chunk to PCM format.
    Based on reference code pattern - ensures proper format for Vosk.
    
    Args:
        audio_chunk: Audio bytes in any format
        audio_format: Format hint (webm, opus, mp4, wav)
        
    Returns:
        Raw PCM audio bytes (16kHz, mono, int16)
    """
    try:
        from pydub import AudioSegment
        import io
        
        if not audio_chunk or len(audio_chunk) == 0:
            print("⚠️ Empty audio chunk received")
            return b''
        
        # Create AudioSegment from bytes
        try:
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_chunk), format=audio_format)
            print(f"✅ Loaded audio segment: {len(audio_segment)}ms, {audio_segment.frame_rate}Hz, {audio_segment.channels} channels")
        except Exception as format_error:
            # Try auto-detect
            print(f"⚠️ Format-specific conversion failed ({format_error}), trying auto-detect...")
            try:
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_chunk))
                print(f"✅ Auto-detected audio: {len(audio_segment)}ms, {audio_segment.frame_rate}Hz, {audio_segment.channels} channels")
            except Exception as auto_error:
                print(f"❌ Audio conversion failed: {auto_error}")
                return b''
        
        # Convert to required format (matching reference code: 16kHz, mono, int16)
        audio_segment = audio_segment.set_frame_rate(SAMPLE_RATE)
        audio_segment = audio_segment.set_channels(1)  # Mono
        audio_segment = audio_segment.set_sample_width(2)  # 16-bit (2 bytes)
        
        pcm_data = audio_segment.raw_data
        print(f"✅ Converted to PCM: {len(pcm_data)} bytes ({len(pcm_data) / (SAMPLE_RATE * 2):.3f}s at 16kHz)")
        return pcm_data
        
    except ImportError:
        print("⚠️ pydub not available. Install with: pip install pydub")
        print("   Also install ffmpeg for WebM/Opus support")
        # pydub not available, return as-is (might already be PCM)
        return audio_chunk
    except Exception as e:
        print(f"❌ Chunk conversion error: {e}")
        import traceback
        traceback.print_exc()
        return audio_chunk

