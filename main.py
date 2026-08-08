import time
import sys
import traceback
from core.logger import logger
from core.database import get_db
from core.input_handler import InputHandler
from core.audio_output import AudioOutput
from core.audio_input import AudioInput
from core.gemini_client import GeminiClient
from core.groq_client import GroqClient

from modes.vocabulary_mode import VocabularyMode
from modes.conversation_mode import ConversationMode
from modes.story_mode import StoryMode

def play_menu(audio_output):
    audio_output.speak("Menu principal.", lang="fr")
    audio_output.speak("Pour le vocabulaire, clic gauche.", lang="fr")
    audio_output.speak("Pour la conversation, clic droit.", lang="fr")
    audio_output.speak("Pour les histoires, bouton latéral avant.", lang="fr")

def select_profile(audio_output, input_handler, db):
    profiles = db.get_profiles()
    if not profiles:
        audio_output.speak("Aucun profil trouvé. Veuillez en créer un.", lang="fr")
        return None
        
    audio_output.speak("Sélection du profil.", lang="fr")
    selected_idx = 0
    
    while True:
        audio_output.speak(profiles[selected_idx]['name'], lang="fr")
        
        event = input_handler.get_event(block=True)
        if not event:
            continue
            
        button, ev_type = event
        if ev_type != "DOWN":
            continue
            
        if button == "LEFT": # Select
            audio_output.speak(f"Bonjour {profiles[selected_idx]['name']}", lang="fr")
            return profiles[selected_idx]['id']
        elif button == "RIGHT": # Next
            selected_idx = (selected_idx + 1) % len(profiles)

def main():
    logger.info("Starting Shakespi...")
    
    try:
        db = get_db()
        input_handler = InputHandler()
        audio_output = AudioOutput()
        audio_input = AudioInput()
        gemini_client = GeminiClient()
        groq_client = GroqClient()
        
        input_handler.start()
        
        audio_output.speak("Démarrage de Shakespi.", lang="fr")
        
        profile_id = select_profile(audio_output, input_handler, db)
        if not profile_id:
            logger.error("No profile selected, exiting.")
            return

        play_menu(audio_output)

        while True:
            event = input_handler.get_event(block=True)
            if not event:
                continue
                
            button, ev_type = event
            if ev_type != "DOWN":
                continue
                
            if button == "LEFT":
                vocab_mode = VocabularyMode(audio_output, input_handler, profile_id)
                vocab_mode.run()
                play_menu(audio_output)
            elif button == "RIGHT":
                conv_mode = ConversationMode(audio_output, audio_input, input_handler, gemini_client, groq_client, profile_id)
                conv_mode.run()
                play_menu(audio_output)
            elif button == "SIDE_FWD":
                story_mode = StoryMode(audio_output, input_handler, gemini_client, profile_id)
                story_mode.run()
                play_menu(audio_output)
            elif button == "MIDDLE":
                play_menu(audio_output)
            elif button == "SIDE_BACK":
                audio_output.speak("Statistiques non implémentées.", lang="fr")
                
    except KeyboardInterrupt:
        logger.info("Shakespi stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        try:
            audio_output.play_error()
        except:
            pass
    finally:
        if 'input_handler' in locals():
            input_handler.stop()
        logger.info("Shakespi shutdown complete.")

if __name__ == "__main__":
    main()
