import sqlite3
import os
from contextlib import contextmanager
from core.logger import logger

class Database:
    def __init__(self, db_path="data/shakespi.db", schema_path="data/schema.sql"):
        self.db_path = db_path
        self.schema_path = schema_path
        self._initialize_db()

    def _initialize_db(self):
        """Initializes the database using the schema file if it doesn't exist."""
        db_exists = os.path.exists(self.db_path)
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with self.get_connection() as conn:
            logger.info(f"Initializing database at {self.db_path}")
            try:
                with open(self.schema_path, 'r', encoding='utf-8') as f:
                    schema_script = f.read()
                conn.executescript(schema_script)
                conn.commit()
                logger.info("Database initialized/updated successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise

    def _is_empty(self, conn):
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        return cursor.fetchone()[0] == 0

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # To return dict-like rows
        try:
            yield conn
        finally:
            conn.close()

    def get_profiles(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM profiles ORDER BY id")
            return cursor.fetchall()
            
    def get_profile(self, profile_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,))
            return cursor.fetchone()

    def log_conversation_message(self, session_id, profile_id, character_name, speaker, content):
        """
        Saves a conversation message turn locally in SQLite.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO conversation_messages (session_id, profile_id, character_name, speaker, content)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, profile_id, character_name, speaker, content))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log conversation message: {e}")

# Global instance
db = None

def init_db(db_path="data/shakespi.db", schema_path="data/schema.sql"):
    global db
    db = Database(db_path, schema_path)
    return db

def get_db():
    if db is None:
        return init_db()
    return db
