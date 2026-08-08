import os
import wave
import yaml
import sounddevice as sd
import soundfile as sf
import queue
import time
from core.logger import logger

class AudioInput:
    def __init__(self, config_path="config/config.example.yaml", mock_audio_path="data/mock_record.wav"):
        self.device_index = None
        self.simulate_input = False
        self.mock_audio_path = mock_audio_path

        if config_path == "config/config.example.yaml" and os.path.exists("config/config.yaml"):
            config_path = "config/config.yaml"

        self._load_config(config_path)

        self.samplerate = 16000 # Whisper prefers 16kHz
        self.channels = 1

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.device_index = config.get("audio_device_index", None)
                self.simulate_input = config.get("simulate_input", False)
        except Exception as e:
            logger.error(f"Failed to load config for audio input: {e}")

        if os.environ.get("SHAKESPI_SIMULATE_INPUT") == "1":
            self.simulate_input = True

    def record_until_event(self, stop_checker, max_duration=30):
        """
        Records audio until the stop_checker() returns True or max_duration is reached.
        stop_checker is a callable that should return True when the button is released.
        Returns the path to the recorded WAV file, or None if failed.
        """
        if self.simulate_input:
            logger.info("Simulation Mode: Injecting mock audio instead of real recording.")
            # Wait for button release to simulate the hold
            start_t = time.time()
            while not stop_checker() and (time.time() - start_t) < max_duration:
                time.sleep(0.1)
                
            if os.path.exists(self.mock_audio_path):
                return self.mock_audio_path
            else:
                logger.warning(f"Mock audio file not found at {self.mock_audio_path}. Returning dummy empty audio.")
                return None

        logger.info("Starting audio recording...")
        q = queue.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio input status: {status}")
            q.put(indata.copy())

        filepath = "data/last_record.wav"
        os.makedirs("data", exist_ok=True)
        
        try:
            # We use an InputStream and pull from the queue
            with sf.SoundFile(filepath, mode='w', samplerate=self.samplerate, channels=self.channels) as file:
                with sd.InputStream(samplerate=self.samplerate, channels=self.channels, 
                                    device=self.device_index, callback=callback):
                    start_time = time.time()
                    while not stop_checker():
                        if (time.time() - start_time) > max_duration:
                            logger.info("Max recording duration reached.")
                            break
                        # Process queued data
                        while not q.empty():
                            file.write(q.get())
                        time.sleep(0.1)
                        
                    # Final flush
                    while not q.empty():
                        file.write(q.get())

            logger.info("Recording finished.")
            return filepath
        except Exception as e:
            logger.error(f"Failed to record audio: {e}")
            return None
