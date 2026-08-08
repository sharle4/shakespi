import sys
import os
import zipfile
import sqlite3
import tempfile
import json
import shutil
from datetime import date

# Add parent dir to path so we can import core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import get_db

def extract_and_import(apkg_path, deck_name):
    if not os.path.exists(apkg_path):
        print(f"Error: File {apkg_path} not found.")
        return

    print(f"Importing deck '{deck_name}' from {apkg_path}...")
    
    db = get_db()

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
        except zipfile.BadZipFile:
            print("Error: Invalid .apkg file (not a zip).")
            return

        # Anki 2.1 collections are usually in 'collection.anki21' or 'collection.anki2'
        anki21_path = os.path.join(temp_dir, 'collection.anki21')
        anki2_path = os.path.join(temp_dir, 'collection.anki2')
        
        db_path = anki21_path if os.path.exists(anki21_path) else anki2_path
        
        if not os.path.exists(db_path):
            print("Error: Could not find Anki database in the package.")
            return

        anki_conn = sqlite3.connect(db_path)
        anki_cursor = anki_conn.cursor()

        try:
            # We want to extract 'notes' which contain the fields
            # Anki schema: notes(id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
            anki_cursor.execute("SELECT flds FROM notes")
            notes = anki_cursor.fetchall()
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Create deck
                cursor.execute("INSERT OR IGNORE INTO decks (name) VALUES (?)", (deck_name,))
                cursor.execute("SELECT id FROM decks WHERE name = ?", (deck_name,))
                deck_id = cursor.fetchone()[0]
                
                cards_added = 0
                for note in notes:
                    fields = note[0].split('\x1f') # Anki fields are separated by 0x1f
                    if len(fields) >= 2:
                        front = fields[0]
                        back = fields[1]
                        example = fields[2] if len(fields) > 2 else None
                        
                        # Strip html tags as we use TTS
                        import re
                        front = re.sub('<[^<]+>', '', front)
                        back = re.sub('<[^<]+>', '', back)
                        if example:
                            example = re.sub('<[^<]+>', '', example)
                        
                        if front and back:
                            cursor.execute("""
                                INSERT INTO cards (deck_id, front, back, example) 
                                VALUES (?, ?, ?, ?)
                            """, (deck_id, front, back, example))
                            cards_added += 1
                
                conn.commit()
                print(f"Successfully imported {cards_added} cards into deck '{deck_name}'.")
                
        except Exception as e:
            print(f"Error reading Anki DB: {e}")
        finally:
            anki_conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python import_anki_deck.py <path_to_apkg> <deck_name>")
        sys.exit(1)
        
    apkg = sys.argv[1]
    name = sys.argv[2]
    extract_and_import(apkg, name)
