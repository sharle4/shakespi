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
        self.model_name = "gemini-flash-latest"
        load_dotenv()
        
        if config_path == "config/config.example.yaml" and os.path.exists("config/config.yaml"):
            config_path = "config/config.yaml"

        self._load_config(config_path)
        
        self.api_key = self.api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL") or self.model_name
        
        if self.api_key and self.api_key != "YOUR_GEMINI_API_KEY_HERE":
            genai.configure(api_key=self.api_key)
            self.is_configured = True
        else:
            logger.warning("Gemini API key is missing or invalid. AI modes will be degraded.")

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                self.api_key = config.get("gemini_api_key", self.api_key)
                self.model_name = config.get("gemini_model", self.model_name)
        except Exception as e:
            logger.error(f"Failed to load config for Gemini from {config_path}: {e}")

    def _get_model_candidates(self):
        user_pref = self.model_name
        pref_candidates = [user_pref]
        if user_pref and not user_pref.startswith("models/"):
            pref_candidates.append(f"models/{user_pref}")

        recommended_models = [
            "gemini-flash-latest",
            "models/gemini-flash-latest",
            "gemini-3.6-flash",
            "models/gemini-3.6-flash",
            "gemini-3.5-flash",
            "models/gemini-3.5-flash",
            "gemini-flash-lite-latest",
            "models/gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "models/gemini-3.5-flash-lite",
            "gemini-pro-latest",
            "models/gemini-pro-latest",
            "gemma-4-31b-it",
            "models/gemma-4-31b-it"
        ]

        dynamic_models = []
        try:
            exclude_keywords = ["tts", "image", "robotics", "lyria", "computer-use", "deep-research", "banana", "customtools"]
            for m in genai.list_models():
                if hasattr(m, 'supported_generation_methods') and 'generateContent' in m.supported_generation_methods:
                    name = m.name
                    if any(k in name.lower() for k in exclude_keywords):
                        continue
                    clean_name = name.replace("models/", "")
                    if name not in dynamic_models:
                        dynamic_models.append(name)
                    if clean_name not in dynamic_models:
                        dynamic_models.append(clean_name)
            if dynamic_models:
                logger.info(f"Discovered Gemini text models from API: {dynamic_models}")
        except Exception as e:
            logger.warning(f"Could not query Gemini model list from API: {e}")

        candidates = []
        for m in pref_candidates + recommended_models + dynamic_models:
            if m and m not in candidates:
                candidates.append(m)
        return candidates

    def generate_conversation_response(self, system_prompt, history, user_message):
        """
        history: list of dicts [{'role': 'user'|'model', 'parts': ['text']}]
        user_message: string
        Returns the text response.
        """
        if not self.is_configured:
            return None
            
        candidates = self._get_model_candidates()
        last_exception = None

        for candidate in candidates:
            try:
                model = genai.GenerativeModel(
                    model_name=candidate,
                    system_instruction=system_prompt
                )
                chat = model.start_chat(history=history)
                response = chat.send_message(user_message)
                if candidate != self.model_name:
                    logger.info(f"Gemini switched to working model: '{candidate}' (was '{self.model_name}')")
                    self.model_name = candidate
                return response.text
            except Exception as e:
                last_exception = e
                err_msg = str(e).lower()
                if any(k in err_msg for k in ["404", "429", "not found", "quota", "limit", "modelservice"]):
                    logger.warning(f"Gemini model '{candidate}' unavailable ({e}). Trying next fallback candidate...")
                    continue
                else:
                    logger.error(f"Gemini conversation error with model '{candidate}': {e}")
                    return None

        logger.error(f"All Gemini model candidates failed. Last error: {last_exception}")
        return None

    def generate_story_scene(self, system_prompt, context):
        """
        Requests the next scene in strict JSON format.
        context: string describing the current state and choices made.
        Returns a dict.
        """
        if not self.is_configured:
            return None
            
        candidates = self._get_model_candidates()
        last_exception = None

        for candidate in candidates:
            try:
                model = genai.GenerativeModel(
                    model_name=candidate,
                    system_instruction=system_prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                response = model.generate_content(context)
                data = json.loads(response.text)
                if candidate != self.model_name:
                    logger.info(f"Gemini switched to working model: '{candidate}' (was '{self.model_name}')")
                    self.model_name = candidate
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Gemini returned invalid JSON using model '{candidate}': {e} - Response: {response.text}")
                return None
            except Exception as e:
                last_exception = e
                err_msg = str(e).lower()
                if any(k in err_msg for k in ["404", "429", "not found", "quota", "limit", "modelservice"]):
                    logger.warning(f"Gemini model '{candidate}' unavailable ({e}). Trying next fallback candidate...")
                    continue
                else:
                    logger.error(f"Gemini story generation error with model '{candidate}': {e}")
                    return None

        logger.error(f"All Gemini model candidates failed for story generation. Last error: {last_exception}")
        return None
