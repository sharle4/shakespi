import time
from core.database import get_db
from core.logger import logger

class ConversationMode:
    def __init__(self, audio_output, audio_input, input_handler, gemini_client, groq_client, profile_id):
        self.audio_output = audio_output
        self.audio_input = audio_input
        self.input_handler = input_handler
        self.gemini_client = gemini_client
        self.groq_client = groq_client
        self.profile_id = profile_id
        self.db = get_db()
        
    def _build_system_prompt(self, character_name=None):
        if character_name:
            role_desc = f"Play the role of {character_name}. Adopt the personality, tone, knowledge, and mannerisms of {character_name}."
        else:
            role_desc = "Play the role of a friendly and encouraging English conversation partner."

        return f"""You are an English conversation partner for a French high school student (14-16 years old). 
Your goals:
1. {role_desc}
2. Use English suitable for an A2/B1 level. Keep sentences short, clear, and natural for your character.
3. If the user makes a significant grammar or vocabulary mistake in their previous turn, briefly point it out and correct it before continuing the conversation in character.
4. Keep the conversation flowing by asking questions consistent with your character.
5. Do NOT use markdown formatting (no asterisks, no bold, no italics, no bullet points) as your text is read aloud by TTS.
"""

    def _prompt_for_character(self):
        """
        Asks the user who they want to talk to.
        Returns the character name string or None for default.
        """
        self.audio_output.speak("Avec qui voulez-vous parler ? Maintenez le clic gauche pour dire un nom, ou clic droit pour le compagnon par défaut.", lang="fr")
        
        attempts = 0
        max_attempts = 2

        while attempts < max_attempts:
            event = self.input_handler.get_event(block=True)
            if not event:
                continue
                
            button, ev_type = event
            
            if button == "RIGHT" and ev_type == "DOWN":
                logger.info("User chose default persona via right click.")
                return None
                
            if button == "LEFT" and ev_type == "DOWN":
                self.audio_output.play_beep()
                
                def stop_checker():
                    ev = self.input_handler.get_event(block=False)
                    if ev:
                        b, t = ev
                        if b == "LEFT" and t == "UP":
                            return True
                    return False
                    
                audio_file = self.audio_input.record_until_event(stop_checker)
                self.audio_output.play_beep()
                
                if audio_file:
                    text = self.groq_client.transcribe(audio_file)
                    if text and len(text.strip()) > 0:
                        char_name = text.strip(". !?")
                        logger.info(f"User requested character: {char_name}")
                        return char_name
                
                attempts += 1
                if attempts < max_attempts:
                    self.audio_output.speak("Je n'ai pas compris le nom. Maintenez le clic gauche pour réessayer, ou clic droit pour le compagnon par défaut.", lang="fr")
                else:
                    self.audio_output.speak("Nom non compris. Utilisation du compagnon par défaut.", lang="fr")
                    return None

        return None

    def run(self):
        logger.info(f"Starting Conversation mode for profile {self.profile_id}")
        
        if not self.gemini_client.is_configured or not self.groq_client.is_configured:
            self.audio_output.speak("Les clés API nécessaires ne sont pas configurées. Ce mode est indisponible.", lang="fr")
            return

        character_name = self._prompt_for_character()
        system_prompt = self._build_system_prompt(character_name)

        if character_name:
            self.audio_output.speak(f"Conversation avec {character_name}. Maintenez le clic gauche pour parler. Clic droit pour quitter.", lang="fr")
        else:
            self.audio_output.speak("Mode conversation. Maintenez le clic gauche pour parler. Clic droit pour quitter.", lang="fr")
        
        history = []
        if character_name:
            initial_user_msg = f"Start the conversation by greeting me in character as {character_name} and asking how I am."
        else:
            initial_user_msg = "Start the conversation by greeting me and asking how I am."

        response = self.gemini_client.generate_conversation_response(
            system_prompt, 
            history, 
            initial_user_msg
        )
        
        if response:
            self.audio_output.speak(response, lang="en")
            history.append({"role": "user", "parts": [initial_user_msg]})
            history.append({"role": "model", "parts": [response]})
        else:
            self.audio_output.play_error()
            return
            
        session_id = self._start_session()
        turns = 0

        while True:
            event = self.input_handler.get_event(block=True)
            if not event:
                continue
                
            button, ev_type = event
            
            if button == "RIGHT" and ev_type == "DOWN":
                self.audio_output.speak("Fin de la conversation. Au revoir !", lang="fr")
                break
                
            if button == "LEFT" and ev_type == "DOWN":
                self.audio_output.play_beep()
                
                def stop_checker():
                    ev = self.input_handler.get_event(block=False)
                    if ev:
                        b, t = ev
                        if b == "LEFT" and t == "UP":
                            return True
                    return False
                
                audio_file = self.audio_input.record_until_event(stop_checker)
                self.audio_output.play_beep()
                
                if audio_file:
                    text = self.groq_client.transcribe(audio_file)
                    if text:
                        logger.info(f"User said: {text}")
                        self.audio_output.play_beep()
                        
                        response = self.gemini_client.generate_conversation_response(
                            system_prompt, history, text
                        )
                        
                        if response:
                            self.audio_output.speak(response, lang="en")
                            history.append({"role": "user", "parts": [text]})
                            history.append({"role": "model", "parts": [response]})
                            turns += 1
                        else:
                            self.audio_output.play_error()
                    else:
                        self.audio_output.speak("Je n'ai pas compris. Pouvez-vous répéter ?", lang="fr")
                else:
                    self.audio_output.play_error()

        self._end_session(session_id, turns)

    def _start_session(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (profile_id, mode) 
                VALUES (?, 'conversation')
            """, (self.profile_id,))
            conn.commit()
            return cursor.lastrowid

    def _end_session(self, session_id, turns):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions 
                SET ended_at = CURRENT_TIMESTAMP, score = ?, summary = ?
                WHERE id = ?
            """, (turns, f"Conversation de {turns} tours.", session_id))
            conn.commit()
