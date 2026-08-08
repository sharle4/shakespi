import os
import json
from core.database import get_db
from core.logger import logger

class StoryMode:
    def __init__(self, audio_output, input_handler, gemini_client, profile_id):
        self.audio_output = audio_output
        self.input_handler = input_handler
        self.gemini_client = gemini_client
        self.profile_id = profile_id
        self.db = get_db()
        
        self.system_prompt = """You are an interactive story generator for an English learner (A2/B1).
Output strictly in JSON format. Do NOT wrap in markdown blocks, just raw JSON.
Format required:
{
  "text": "The story text here...",
  "vocabulary_pause": "A difficult word from the text and its French translation.",
  "choices": [
    "Choice 1 text...",
    "Choice 2 text..."
  ]
}
Ensure the text is engaging and choices are clear. Do not use markdown formatting (no asterisks, no bold) inside the JSON text fields as they will be read aloud by TTS. Keep the story moving. If choices is empty, it means the story is over."""

    def run(self):
        logger.info(f"Starting Story mode for profile {self.profile_id}")
        
        # Menu for stories
        stories = self._list_local_stories()
        ai_available = self.gemini_client.is_configured
        
        options = []
        for s in stories:
            options.append(s)
        if ai_available:
            options.append({"id": "ai_gen", "name": "Histoire infinie générée par IA"})
            
        if not options:
            self.audio_output.speak("Aucune histoire disponible.", lang="fr")
            return
            
        self.audio_output.speak("Choisissez une histoire.", lang="fr")
        
        selected_idx = 0
        while True:
            # Announce current selection
            self.audio_output.speak(options[selected_idx]['name'], lang="fr")
            
            event = self.input_handler.get_event(block=True)
            if not event:
                continue
            
            button, ev_type = event
            if ev_type != "DOWN":
                continue
                
            if button == "SIDE_FWD": # next
                selected_idx = (selected_idx + 1) % len(options)
            elif button == "SIDE_BACK": # prev
                selected_idx = (selected_idx - 1) % len(options)
            elif button == "LEFT": # select
                break
            elif button == "RIGHT": # quit
                return
                
        selected_story = options[selected_idx]
        
        session_id = self._start_session()
        
        if selected_story['id'] == 'ai_gen':
            self._run_ai_story()
        else:
            self._run_local_story(selected_story['path'])
            
        self._end_session(session_id)

    def _list_local_stories(self):
        stories_dir = "data/stories"
        if not os.path.exists(stories_dir):
            return []
            
        stories = []
        for f in os.listdir(stories_dir):
            if f.endswith('.json'):
                path = os.path.join(stories_dir, f)
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        stories.append({
                            "id": data.get("id", f),
                            "name": data.get("title", f),
                            "path": path
                        })
                except Exception as e:
                    logger.error(f"Error loading story {f}: {e}")
        return stories

    def _run_local_story(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                story_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load story from {path}: {e}")
            self.audio_output.play_error()
            return
            
        scenes = {scene['id']: scene for scene in story_data.get('scenes', [])}
        current_scene_id = story_data.get('start_scene', 'start')
        
        while current_scene_id in scenes:
            scene = scenes[current_scene_id]
            self.audio_output.speak(scene['text'], lang="en")
            
            choices = scene.get('choices', [])
            if not choices:
                self.audio_output.speak("Fin de l'histoire.", lang="fr")
                break
                
            # Announce choices
            for i, choice in enumerate(choices):
                self.audio_output.speak(f"Choix {i+1} : {choice['text']}", lang="en")
                
            # Wait for selection
            choice_idx = self._wait_for_choice(len(choices))
            if choice_idx == -1: # Quit
                break
            elif choice_idx == -2: # Repeat
                continue # Will loop and repeat scene
                
            current_scene_id = choices[choice_idx]['next_scene']

    def _run_ai_story(self):
        context = "Start a completely new story about an adventure in a fantasy world. Provide the first scene and choices."
        
        while True:
            self.audio_output.play_beep()
            scene_data = self.gemini_client.generate_story_scene(self.system_prompt, context)
            
            if not scene_data:
                self.audio_output.play_error()
                break
                
            text = scene_data.get("text", "")
            choices = scene_data.get("choices", [])
            vocab = scene_data.get("vocabulary_pause", "")
            
            self.audio_output.speak(text, lang="en")
            
            if not choices:
                self.audio_output.speak("Fin de l'histoire.", lang="fr")
                break
                
            for i, choice in enumerate(choices):
                self.audio_output.speak(f"Choix {i+1} : {choice}", lang="en")
                
            choice_idx = self._wait_for_choice(len(choices), vocab)
            if choice_idx == -1: # Quit
                break
            elif choice_idx == -2: # Repeat
                continue # In AI mode, this is tricky. We'd have to cache the last scene data. For now let's just proceed or implement basic repeat.
                
            # Append context
            context = f"Previous scene: {text}\nUser chose: {choices[choice_idx]}\nContinue the story based on this choice."

    def _wait_for_choice(self, num_choices, vocab=None):
        while True:
            event = self.input_handler.get_event(block=True)
            if not event:
                continue
                
            button, ev_type = event
            if ev_type != "DOWN":
                continue
                
            if button == "LEFT" and num_choices >= 1:
                return 0
            elif button == "RIGHT" and num_choices >= 2:
                return 1
            elif button == "SIDE_FWD" and num_choices >= 3:
                return 2
            elif button == "MIDDLE":
                # Double click to quit, single click to repeat. Let's simplify: middle = repeat
                return -2
            elif button == "SIDE_BACK":
                if vocab:
                    self.audio_output.speak("Pause vocabulaire.", lang="fr")
                    self.audio_output.speak(vocab, lang="en")
                else:
                    return -1 # Quit

    def _start_session(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (profile_id, mode) 
                VALUES (?, 'story')
            """, (self.profile_id,))
            conn.commit()
            return cursor.lastrowid

    def _end_session(self, session_id):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions 
                SET ended_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (session_id,))
            conn.commit()
