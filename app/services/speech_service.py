import os
import io
import logging
import tempfile
import asyncio
from typing import Optional
import wave

logger = logging.getLogger(__name__)

class SpeechService:
    def __init__(self):
        self.whisper_available = False
        self.tts_available = False
        
        # Initialize Whisper for STT
        try:
            import whisper
            self.whisper_model = whisper.load_model("base")
            self.whisper_available = True
            logger.info("Whisper model loaded successfully")
        except ImportError:
            logger.warning("Whisper not available, STT will use placeholder")
        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}")
        
        # Initialize TTS
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)  # Speed of speech
            self.tts_engine.setProperty('volume', 0.9)  # Volume level
            self.tts_available = True
            logger.info("TTS engine initialized successfully")
        except ImportError:
            logger.warning("pyttsx3 not available, TTS will use placeholder")
        except Exception as e:
            logger.error(f"Error initializing TTS engine: {e}")
    
    async def speech_to_text(self, audio_data: bytes) -> str:
        """Convert speech audio to text"""
        if not self.whisper_available:
            return "[Speech recognition not available - placeholder text]"
        
        try:
            # Save audio data to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            # Use Whisper to transcribe
            result = self.whisper_model.transcribe(temp_file_path)
            transcribed_text = result["text"].strip()
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            return transcribed_text if transcribed_text else "[No speech detected]"
            
        except Exception as e:
            logger.error(f"Error in speech-to-text conversion: {e}")
            return "[Error in speech recognition]"
    
    async def text_to_speech(self, text: str) -> bytes:
        """Convert text to speech audio"""
        if not self.tts_available:
            # Return empty audio data as placeholder
            return self._generate_placeholder_audio()
        
        try:
            # Create temporary file for audio output
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file_path = temp_file.name
            
            # Generate speech
            self.tts_engine.save_to_file(text, temp_file_path)
            self.tts_engine.runAndWait()
            
            # Read the generated audio file
            with open(temp_file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Error in text-to-speech conversion: {e}")
            return self._generate_placeholder_audio()
    
    def _generate_placeholder_audio(self) -> bytes:
        """Generate a short placeholder audio file"""
        try:
            # Create a short silent WAV file
            sample_rate = 44100
            duration = 1.0  # 1 second
            frames = int(sample_rate * duration)
            
            # Create WAV file in memory
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                
                # Write silent frames
                silent_frames = b'\x00\x00' * frames
                wav_file.writeframes(silent_frames)
            
            buffer.seek(0)
            return buffer.read()
            
        except Exception as e:
            logger.error(f"Error generating placeholder audio: {e}")
            return b''
    
    def is_speech_available(self) -> bool:
        """Check if speech services are available"""
        return self.whisper_available and self.tts_available
    
    def get_speech_status(self) -> dict:
        """Get status of speech services"""
        return {
            'whisper_available': self.whisper_available,
            'tts_available': self.tts_available,
            'fully_functional': self.whisper_available and self.tts_available
        }

