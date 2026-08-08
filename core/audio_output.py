import os
import subprocess
import hashlib
import yaml
import re
import sounddevice as sd
import soundfile as sf
import numpy as np
from core.logger import logger

class AudioOutput:
    def __init__(self, config_path="config/config.example.yaml", cache_dir="data/tts_cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.voice_fr = "fr_FR-upmc-medium.onnx"
        self.voice_en = "en_US-lessac-medium.onnx"
        self.device_index = None
        self.piper_bin = "piper" # Assumes piper is in PATH or alias

        if config_path == "config/config.example.yaml" and os.path.exists("config/config.yaml"):
            config_path = "config/config.yaml"

        self._load_config(config_path)

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.voice_fr = config.get("piper_voice_fr", self.voice_fr)
                self.voice_en = config.get("piper_voice_en", self.voice_en)
                self.device_index = config.get("audio_device_index", None)
        except Exception as e:
            logger.error(f"Failed to load config for audio output: {e}")

    def _clean_text(self, text):
        if not text:
            return ""
        # Remove asterisks (*), hashtags (#), underscores (_), and markdown list markers
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'#+\s*', '', text)
        text = re.sub(r'_+', '', text)
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def generate_tts(self, text, lang="en"):
        """
        Generates TTS audio and returns the path to the cached WAV file.
        """
        text = self._clean_text(text)
        if not text:
            return None

        # Hash the text and language to create a cache key
        hash_obj = hashlib.md5(f"{lang}:{text}".encode('utf-8'))
        filename = f"{hash_obj.hexdigest()}.wav"
        filepath = os.path.join(self.cache_dir, filename)

        if os.path.exists(filepath):
            logger.debug(f"TTS cache hit for: '{text[:20]}...'")
            return filepath

        logger.info(f"Generating TTS ({lang}): '{text[:30]}...'")
        voice = self.voice_fr if lang == "fr" else self.voice_en
        
        # Determine paths
        voice_path = os.path.join("models", voice)
        
        if not os.path.exists(voice_path):
            logger.warning(f"Voice model {voice_path} not found. Ensure models are downloaded.")
            # We don't crash, but it won't work unless piper finds it somewhere else
            
        try:
            # We use subprocess to call the piper CLI
            # piper --model <voice.onnx> --output_file <filepath>
            cmd = [
                self.piper_bin,
                "--model", voice_path,
                "--output_file", filepath
            ]
            
            # Pass the text to piper via stdin
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            _, stderr = process.communicate(input=text.encode('utf-8'))
            
            if process.returncode != 0:
                logger.error(f"Piper TTS failed: {stderr.decode('utf-8')}")
                return None
                
            return filepath
        except FileNotFoundError:
            logger.error("Piper binary not found. Please make sure piper is installed and in PATH.")
            return None
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            return None

    def play_file(self, filepath):
        """
        Plays a WAV file using sounddevice. Blocks until finished.
        """
        if not filepath or not os.path.exists(filepath):
            logger.error(f"File to play not found: {filepath}")
            return

        try:
            data, fs = sf.read(filepath)
            
            # Convert to float32 to avoid sounddevice warnings/issues
            if data.dtype != 'float32':
                data = data.astype('float32')

            logger.debug(f"Playing audio: {filepath}")
            if self.device_index is not None:
                sd.play(data, fs, device=self.device_index)
            else:
                sd.play(data, fs)
            sd.wait() # Wait until file is done playing
        except Exception as e:
            logger.error(f"Failed to play audio file {filepath}: {e}")

    def speak(self, text, lang="en"):
        """
        Generates (or retrieves) TTS and plays it.
        """
        filepath = self.generate_tts(text, lang)
        if filepath:
            self.play_file(filepath)

    def play_error(self):
        """Play a generic error message"""
        self.speak("Une erreur est survenue.", lang="fr")
        
    def play_beep(self):
        """Play a simple synthetic beep for processing feedback"""
        try:
            fs = 44100 # Hz
            duration = 0.1 # seconds
            f = 440.0 # sine frequency
            t = np.linspace(0, duration, int(fs * duration), False)
            audio = np.sin(f * 2 * np.pi * t)
            
            if self.device_index is not None:
                sd.play(audio, fs, device=self.device_index)
            else:
                sd.play(audio, fs)
            sd.wait()
        except Exception as e:
            logger.error(f"Failed to play beep: {e}")
