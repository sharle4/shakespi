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
        
        self.system_prompt = """You are an English conversation partner for a French high school student (14-16 years old). 
Your goals:
1. Play the role of the character in the current scenario.
2. Use English suitable for an A2/B1 level. Keep sentences short and clear.
3. If the user makes a significant grammar or vocabulary mistake in their previous turn, briefly point it out and correct it before continuing the conversation.
4. Keep the conversation flowing by asking questions.
"""

    def run(self):
        logger.info(f"Starting Conversation mode for profile {self.profile_id}")
        
        if not self.gemini_client.is_configured or not self.groq_client.is_configured:
            self.audio_output.speak("Les clés API nécessaires ne sont pas configurées. Ce mode est indisponible.", lang="fr")
            return
            
        self.audio_output.speak("Mode conversation. Maintenez le clic gauche pour parler. Clic droit pour quitter.", lang="fr")
        
        # We start a conversation
        history = []
        
        # Initial greeting from Gemini based on the system prompt
        initial_user_msg = "Start the conversation by greeting me and asking how I am."
        response = self.gemini_client.generate_conversation_response(
            self.system_prompt, 
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
            # Wait for user to start recording or quit
            event = self.input_handler.get_event(block=True)
            if not event:
                continue
                
            button, ev_type = event
            
            if button == "RIGHT" and ev_type == "DOWN":
                # Quit
                self.audio_output.speak("Fin de la conversation. Au revoir !", lang="fr")
                break
                
            if button == "LEFT" and ev_type == "DOWN":
                # Start recording
                self.audio_output.play_beep()
                
                def stop_checker():
                    # We drain the queue to see if LEFT was released
                    # Note: we need a non-blocking way to check
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
                        self.audio_output.play_beep() # indicate processing
                        
                        response = self.gemini_client.generate_conversation_response(
                            self.system_prompt, history, text
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
