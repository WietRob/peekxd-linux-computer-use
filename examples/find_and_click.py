"""Example: Find a UI element and click it."""
from peekxd.inspection import get_inspection_provider
from peekxd.input import get_input_provider

# Find the "Submit" button
inspector = get_inspection_provider()
elem = inspector.find_element(name="Submit")
if elem:
    print(f"Found '{elem.name}' at {elem.position}")
    # Click it
    input_ctl = get_input_provider()
    input_ctl.click(elem.position[0], elem.position[1])
    print("Clicked!")
else:
    print("Element not found")
