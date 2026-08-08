import yaml
import os
import requests
from core.logger import logger
from dotenv import load_dotenv

class GroqClient:
    def __init__(self, config_path="config/config.example.yaml"):
        self.api_key = None
        self.is_configured = False
        self.model = "whisper-large-v3-turbo"
        self.api_url = "https://api.groq.com/openai/v1/audio/transcriptions"
        
        load_dotenv()
        self._load_config(config_path)
        
        self.api_key = self.api_key or os.getenv("GROQ_API_KEY")
        
        if self.api_key and self.api_key != "YOUR_GROQ_API_KEY_HERE":
            self.is_configured = True
        else:
            logger.warning("Groq API key is missing or invalid. Conversation mode will be degraded.")

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.api_key = config.get("groq_api_key", None)
                self.model = config.get("groq_model", self.model)
        except Exception as e:
            logger.error(f"Failed to load config for Groq: {e}")

    def transcribe(self, audio_filepath):
        """
        Transcribes the audio file using Groq's speech-to-text API.
        Returns the transcribed text string or None on failure.
        """
        if not self.is_configured:
            return None
            
        if not os.path.exists(audio_filepath):
            logger.error(f"Audio file to transcribe not found: {audio_filepath}")
            return None
            
        logger.info(f"Transcribing {audio_filepath} via Groq...")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            with open(audio_filepath, 'rb') as f:
                files = {
                    'file': (os.path.basename(audio_filepath), f, 'audio/wav')
                }
                data = {
                    'model': self.model,
                    'language': 'en' # Assuming english for learning, or we can make it dynamic
                }
                
                response = requests.post(self.api_url, headers=headers, files=files, data=data, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get('text', '').strip()
                else:
                    logger.error(f"Groq API error ({response.status_code}): {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Groq transcription error: {e}")
            return None
