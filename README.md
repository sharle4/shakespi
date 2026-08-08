# Shakespi

Shakespi is a headless English learning device designed to run on a Raspberry Pi 4B, controlled entirely by a 5-button USB mouse and voice.

## Architecture

The system is separated into core modules:
- **`core/input_handler.py`**: A dedicated thread reads mouse events via `evdev` (or keyboard events on Windows) and pushes them to a thread-safe Queue. This ensures that the application never misses a click, even if the main loop is blocked playing an audio file or waiting for an API response.
- **`core/audio_output.py`**: Uses `piper-tts` binary to generate `.wav` files locally, and plays them via `sounddevice`.
- **`core/audio_input.py`**: Records the user's voice using `sounddevice` while a button is held down. Can inject a mock `.wav` file on PC for testing.
- **`core/database.py`**: SQLite database managing profiles, sessions, decks, and SM-2 spaced repetition progress.
- **`core/gemini_client.py` & `core/groq_client.py`**: AI handlers for conversation generation (Gemini 1.5 Flash) and speech-to-text (Groq Whisper).

## Simulation Mode (PC Development)

Since developing on a Raspberry Pi without a screen is tedious, you can run the entire application on your PC using the keyboard to simulate the mouse:

1. Install requirements: `pip install -r requirements.txt` (or install manually: `keyboard`, `sounddevice`, `soundfile`, `pyyaml`, `google-generativeai`, `requests`).
2. Set the environment variable: `set SHAKESPI_SIMULATE_INPUT=1` (Windows) or `export SHAKESPI_SIMULATE_INPUT=1` (Linux/Mac).
3. Run: `python main.py`

### Keyboard Mapping:
- **Left Click**: Left Arrow
- **Right Click**: Right Arrow
- **Middle Click**: Space
- **Side Forward**: Up Arrow
- **Side Back**: Down Arrow

*(These mappings can be customized in `config/button_mapping.yaml`)*

## Adding Stories

To add a new offline story, create a `.json` file in `data/stories/` following the format of `example_story_1.json`.

## Adding Anki Decks

You can import an Anki `.apkg` file using the provided script:
`python scripts/import_anki_deck.py path/to/deck.apkg "Deck Name"`