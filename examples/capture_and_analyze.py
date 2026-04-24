"""Example: Capture screen and analyze with AI vision."""
from peekxd.screenshot import get_screenshot_provider
from peekxd.vision import get_vision_provider

# Capture full screen
screenshot = get_screenshot_provider()
path = screenshot.capture_screen("/tmp/screen.png")
print(f"Captured: {path}")

# Analyze with AI
vision = get_vision_provider()
result = vision.analyze(path, "Describe what you see on this screen")
print(f"Analysis: {result}")
