"""Example: Automate opening an app and typing."""
from peekxd.window import get_window_provider
from peekxd.input import get_input_provider
from time import sleep

# Launch Firefox
window = get_window_provider()
window.launch_app("firefox")
sleep(2)

# Type a URL
input_ctl = get_input_provider()
input_ctl.type_text("github.com/peekxd-linux/peekxd")
input_ctl.key_press("Return")
sleep(3)

# Take screenshot
from peekxd.screenshot import get_screenshot_provider
screenshot = get_screenshot_provider()
path = screenshot.capture_screen("/tmp/firefox.png")
print(f"Screenshot saved: {path}")
