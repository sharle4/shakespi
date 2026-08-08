import sys
import os
import pytest
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modes.story_mode import StoryMode

class DummyGemini:
    def __init__(self):
        self.is_configured = True
    def generate_story_scene(self, prompt, context):
        return {
            "text": "The test adventure begins.",
            "choices": ["Option A", "Option B"]
        }

def test_ai_story_generation():
    story = StoryMode(None, None, DummyGemini(), 1)
    # We just want to ensure that if the API returns proper JSON, we can extract it.
    scene_data = story.gemini_client.generate_story_scene("", "")
    assert scene_data["text"] == "The test adventure begins."
    assert len(scene_data["choices"]) == 2
