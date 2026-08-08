import threading
import queue
import time
import yaml
import os
from core.logger import logger

class InputHandler:
    def __init__(self, config_path="config/config.example.yaml", mapping_path="config/button_mapping.yaml"):
        self.event_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.simulate_input = False
        
        if config_path == "config/config.example.yaml" and os.path.exists("config/config.yaml"):
            config_path = "config/config.yaml"

        self._load_config(config_path)
        self._load_mapping(mapping_path)
        
        self.input_thread = None

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.simulate_input = config.get('simulate_input', False)
        except Exception as e:
            logger.error(f"Failed to load config {config_path}: {e}")
            self.simulate_input = False
            
        # Environment variable override
        if os.environ.get("SHAKESPI_SIMULATE_INPUT") == "1":
            self.simulate_input = True
            
        logger.info(f"Input mode: {'Simulation (Keyboard)' if self.simulate_input else 'Hardware (Mouse)'}")

    def _load_mapping(self, mapping_path):
        self.mapping = {}
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                raw_mapping = yaml.safe_load(f)
            
            # Create a reverse mapping: physical_button -> list of logical_actions
            # Actually, the active logic action depends on the current state (Mode).
            # The input handler just emits raw generic buttons, or we map physical -> logical in the app?
            # A better approach: input handler emits the physical button (e.g. "LEFT", "RIGHT"), 
            # and the main loop uses the button_mapping to resolve it to an action for the current mode.
            
            # Let's map physical inputs to standard internal button names:
            # LEFT, RIGHT, MIDDLE, SIDE_FWD, SIDE_BACK
            
            self.keyboard_to_button = {}
            self.evdev_to_button = {
                272: "LEFT",   # BTN_LEFT
                273: "RIGHT",  # BTN_RIGHT
                274: "MIDDLE", # BTN_MIDDLE
                275: "SIDE_BACK", # BTN_SIDE
                276: "SIDE_FWD"   # BTN_EXTRA
            }
            
            # Build keyboard reverse mapping from the yaml
            for action, data in raw_mapping.items():
                if 'mouse' in data and 'keyboard' in data:
                    self.keyboard_to_button[data['keyboard']] = data['mouse']
                    
            logger.info("Button mapping loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load mapping {mapping_path}: {e}")

    def start(self):
        self._stop_event.clear()
        if self.simulate_input:
            self.input_thread = threading.Thread(target=self._keyboard_listener_loop, daemon=True)
        else:
            self.input_thread = threading.Thread(target=self._evdev_listener_loop, daemon=True)
        self.input_thread.start()

    def stop(self):
        self._stop_event.set()
        if self.input_thread and self.input_thread.is_alive():
            # In simulation mode, keyboard.wait might block. 
            # We don't strictly need to join if it's daemon, but let's be clean.
            pass

    def get_event(self, block=True, timeout=None):
        """
        Returns a tuple: (button_name, event_type)
        button_name: "LEFT", "RIGHT", "MIDDLE", "SIDE_FWD", "SIDE_BACK"
        event_type: "DOWN", "UP"
        Returns None if queue is empty (when block=False or timeout reached)
        """
        try:
            return self.event_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def _keyboard_listener_loop(self):
        try:
            import keyboard
        except ImportError:
            logger.error("keyboard package is required for simulation mode. pip install keyboard")
            return

        logger.info("Keyboard simulation listener started.")
        
        # We need a way to hook all keys and push those that match our mapping
        def on_key_event(e):
            if e.name in self.keyboard_to_button:
                button = self.keyboard_to_button[e.name]
                event_type = "DOWN" if e.event_type == keyboard.KEY_DOWN else "UP"
                self.event_queue.put((button, event_type))

        keyboard.hook(on_key_event)
        
        while not self._stop_event.is_set():
            time.sleep(0.1)
            
        keyboard.unhook_all()

    def _evdev_listener_loop(self):
        try:
            import evdev
        except ImportError:
            logger.error("evdev package is required for hardware mode. Are you on Linux?")
            return

        # Find the mouse device
        mouse_dev = None
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for device in devices:
            # Simple heuristic to find a mouse
            if "mouse" in device.name.lower() or "usb" in device.name.lower():
                # Verify it has button capabilities
                cap = device.capabilities()
                if evdev.ecodes.EV_KEY in cap and evdev.ecodes.BTN_LEFT in cap[evdev.ecodes.EV_KEY]:
                    mouse_dev = device
                    break
        
        if not mouse_dev:
            # Fallback
            for device in devices:
                cap = device.capabilities()
                if evdev.ecodes.EV_KEY in cap and evdev.ecodes.BTN_LEFT in cap[evdev.ecodes.EV_KEY]:
                    mouse_dev = device
                    break

        if not mouse_dev:
            logger.error("No compatible mouse device found via evdev.")
            return

        logger.info(f"Mouse listener started on {mouse_dev.path} ({mouse_dev.name})")

        # Set device to non-blocking or use select, but since we are in a thread, 
        # we can just use the blocking read_loop, checking stop_event periodically
        # Actually read_loop is blocking, so we'll use a timeout approach.
        
        # To avoid blocking forever, we use select
        import select
        while not self._stop_event.is_set():
            r, w, x = select.select([mouse_dev.fd], [], [], 0.1)
            if r:
                for event in mouse_dev.read():
                    if event.type == evdev.ecodes.EV_KEY:
                        if event.code in self.evdev_to_button:
                            button = self.evdev_to_button[event.code]
                            event_type = "DOWN" if event.value == 1 else ("UP" if event.value == 0 else "HOLD")
                            if event_type in ("DOWN", "UP"):
                                self.event_queue.put((button, event_type))
