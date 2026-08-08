import yaml
import json
import google.generativeai as genai
from core.logger import logger
import os
from dotenv import load_dotenv

class GeminiClient:
    def __init__(self, config_path="config/config.example.yaml"):
        self.api_key = None
        self.is_configured = False
        load_dotenv()
        self._load_config(config_path)
        
        self.api_key = self.api_key or os.getenv("GEMINI_API_KEY")
        
        if self.api_key and self.api_key != "YOUR_GEMINI_API_KEY_HERE":
            genai.configure(api_key=self.api_key)
            # Use Flash for fast conversational and JSON generation
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.is_configured = True
        else:
            logger.warning("Gemini API key is missing or invalid. AI modes will be degraded.")

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.api_key = config.get("gemini_api_key", None)
        except Exception as e:
            logger.error(f"Failed to load config for Gemini: {e}")

    def generate_conversation_response(self, system_prompt, history, user_message):
        """
        history: list of dicts [{'role': 'user'|'model', 'parts': ['text']}]
        user_message: string
        Returns the text response.
        """
        if not self.is_configured:
            return None
            
        try:
            # We construct a chat session
            # Note: The system prompt might need to be injected into the first user message or set in the model
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=system_prompt
            )
            chat = model.start_chat(history=history)
            response = chat.send_message(user_message)
            return response.text
        except Exception as e:
            logger.error(f"Gemini conversation error: {e}")
            return None

    def generate_story_scene(self, system_prompt, context):
        """
        Requests the next scene in strict JSON format.
        context: string describing the current state and choices made.
        Returns a dict.
        """
        if not self.is_configured:
            return None
            
        try:
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=system_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content(context)
            data = json.loads(response.text)
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Gemini returned invalid JSON: {e} - Response: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Gemini story generation error: {e}")
            return None
