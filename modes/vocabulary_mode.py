import time
from datetime import datetime, date, timedelta
from core.database import get_db
from core.logger import logger
import yaml

class VocabularyMode:
    def __init__(self, audio_output, input_handler, profile_id, config_path="config/config.example.yaml"):
        self.audio_output = audio_output
        self.input_handler = input_handler
        self.profile_id = profile_id
        self.db = get_db()
        self.daily_new_cards_limit = 20
        self.max_reviews_per_session = 50
        
        self._load_config(config_path)

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.daily_new_cards_limit = config.get("daily_new_cards_limit", self.daily_new_cards_limit)
                self.max_reviews_per_session = config.get("max_reviews_per_session", self.max_reviews_per_session)
        except Exception as e:
            logger.error(f"Failed to load config in vocab mode: {e}")

    def get_due_cards(self):
        """Fetches due cards up to the max_reviews_per_session limit."""
        today = date.today().isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Fetch cards that are due today or overdue
            cursor.execute("""
                SELECT * FROM cards 
                WHERE next_review_date <= ? 
                ORDER BY next_review_date ASC
                LIMIT ?
            """, (today, self.max_reviews_per_session))
            return [dict(row) for row in cursor.fetchall()]

    def update_card_sm2(self, card, rating):
        """
        SM-2 Algorithm implementation.
        rating: 1 (Again), 2 (Hard), 3 (Good), 4 (Easy)
        """
        repetitions = card['repetitions']
        ease_factor = card['ease_factor']
        interval = card['interval']
        
        # SM-2 rating mapping (0-5 scale in original SM-2)
        # We map our 1-4 buttons to: 
        # 1 -> 0 (Blackout) or 1 (Wrong)
        # 2 -> 3 (Hard)
        # 3 -> 4 (Good)
        # 4 -> 5 (Easy)
        q = 0
        if rating == 1: q = 0
        elif rating == 2: q = 3
        elif rating == 3: q = 4
        elif rating == 4: q = 5

        if q < 3:
            repetitions = 0
            interval = 1
        else:
            if repetitions == 0:
                interval = 1
            elif repetitions == 1:
                interval = 6
            else:
                interval = round(interval * ease_factor)
            repetitions += 1

        ease_factor = ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        if ease_factor < 1.3:
            ease_factor = 1.3

        next_review_date = (date.today() + timedelta(days=interval)).isoformat()
        today = date.today().isoformat()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE cards 
                SET interval = ?, ease_factor = ?, repetitions = ?, 
                    next_review_date = ?, last_reviewed_date = ?
                WHERE id = ?
            """, (interval, ease_factor, repetitions, next_review_date, today, card['id']))
            
            cursor.execute("""
                INSERT INTO review_logs (profile_id, card_id, rating) 
                VALUES (?, ?, ?)
            """, (self.profile_id, card['id'], rating))
            conn.commit()

    def run(self):
        logger.info(f"Starting Vocabulary mode for profile {self.profile_id}")
        
        cards = self.get_due_cards()
        if not cards:
            self.audio_output.speak("Aucune carte à réviser pour le moment. Bravo !", lang="fr")
            return

        self.audio_output.speak(f"Vous avez {len(cards)} cartes à réviser.", lang="fr")
        
        cards_reviewed = 0
        session_id = self._start_session()

        for card in cards:
            quit_requested = self._review_card(card)
            if quit_requested:
                break
            cards_reviewed += 1
            
        # Summary
        self.audio_output.speak(f"Session terminée. Vous avez révisé {cards_reviewed} cartes.", lang="fr")
        self._end_session(session_id, cards_reviewed)
        
    def _review_card(self, card):
        """
        Review loop for a single card.
        Returns True if the user wants to quit the session early, False otherwise.
        """
        # Read the front of the card (English)
        self.audio_output.speak(card['front'], lang="en")
        
        while True:
            event = self.input_handler.get_event(block=True)
            if not event:
                continue
            
            button, ev_type = event
            if ev_type != "DOWN":
                continue

            # Need to map physical button to vocab action
            # Simplified for now assuming logical mapping from button_mapping:
            # We can use the button string directly or abstract it.
            # config mapping:
            # ACTION_VOCAB_FLIP: "LEFT", ACTION_VOCAB_REPEAT: "MIDDLE", ACTION_VOCAB_QUIT: "MIDDLE" (hold)
            
            if button == "LEFT": # Flip
                self._reveal_card(card)
                return self._wait_for_rating(card)
            elif button == "MIDDLE": # Repeat
                self.audio_output.speak(card['front'], lang="en")
            elif button == "RIGHT": # Fallback to flip if they press something else
                self._reveal_card(card)
                return self._wait_for_rating(card)

    def _reveal_card(self, card):
        # We assume back is French
        self.audio_output.speak(card['back'], lang="fr")
        if card['example']:
            self.audio_output.speak("Par exemple :", lang="fr")
            self.audio_output.speak(card['example'], lang="en")

    def _wait_for_rating(self, card):
        """
        Waits for the user to rate the card.
        Returns True if quit requested.
        """
        # "Again" = LEFT, "Hard" = RIGHT, "Good" = SIDE_FWD, "Easy" = SIDE_BACK
        while True:
            event = self.input_handler.get_event(block=True)
            if not event:
                continue
                
            button, ev_type = event
            if ev_type != "DOWN":
                continue

            if button == "LEFT":
                self.audio_output.play_beep()
                self.update_card_sm2(card, 1)
                return False
            elif button == "RIGHT":
                self.audio_output.play_beep()
                self.update_card_sm2(card, 2)
                return False
            elif button == "SIDE_FWD":
                self.audio_output.play_beep()
                self.update_card_sm2(card, 3)
                return False
            elif button == "SIDE_BACK":
                self.audio_output.play_beep()
                self.update_card_sm2(card, 4)
                return False
            elif button == "MIDDLE":
                # Double press or something could mean quit. Let's say middle means quit rating and exit session.
                self.audio_output.play_beep()
                return True

    def _start_session(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (profile_id, mode) 
                VALUES (?, 'vocabulary')
            """, (self.profile_id,))
            conn.commit()
            return cursor.lastrowid

    def _end_session(self, session_id, cards_reviewed):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions 
                SET ended_at = CURRENT_TIMESTAMP, score = ?
                WHERE id = ?
            """, (cards_reviewed, session_id))
            conn.commit()
