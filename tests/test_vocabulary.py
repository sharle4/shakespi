import sys
import os
import pytest
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import Database
from modes.vocabulary_mode import VocabularyMode

@pytest.fixture
def test_db():
    # Use in-memory DB for tests
    db = Database(db_path=":memory:", schema_path="data/schema.sql")
    # Add a deck and card
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO decks (name) VALUES ('Test Deck')")
        cursor.execute("""
            INSERT INTO cards (deck_id, front, back, interval, ease_factor, repetitions, next_review_date)
            VALUES (1, 'Hello', 'Bonjour', 0, 2.5, 0, ?)
        """, (date.today().isoformat(),))
        conn.commit()
    return db

class DummyAudioOutput:
    def speak(self, text, lang="en"):
        pass
    def play_beep(self):
        pass
    def play_error(self):
        pass

class DummyInputHandler:
    def __init__(self, sequence):
        self.sequence = sequence
        self.idx = 0
    def get_event(self, block=True):
        if self.idx < len(self.sequence):
            res = self.sequence[self.idx]
            self.idx += 1
            return res
        return None

def test_sm2_algorithm(test_db):
    vocab = VocabularyMode(DummyAudioOutput(), DummyInputHandler([]), 1, "config/config.example.yaml")
    vocab.db = test_db
    
    cards = vocab.get_due_cards()
    assert len(cards) == 1
    
    # Simulate a Good rating (3)
    vocab.update_card_sm2(cards[0], 3)
    
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE id=1")
        updated_card = dict(cursor.fetchone())
        
        assert updated_card['repetitions'] == 1
        assert updated_card['interval'] == 1 # First repetition with q=4
        assert updated_card['ease_factor'] > 2.3
