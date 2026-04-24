"""Screen markup utilities for peekxd Linux.

Provides bounding box drawing and screen analysis with visual element markup.
This allows agents to see exactly where UI elements are located.
"""

import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from ..core.errors import peekxdError, VisionError


def draw_bounding_boxes(
    image_path: str,
    elements: List[Dict[str, Any]],
    output_path: Optional[str] = None,
    box_color: str = "#FF0000",
    label_color: str = "#FFFFFF",
    box_width: int = 2,
    font_size: int = 12,
) -> str:
    """Draw numbered bounding boxes around detected elements on a screenshot.

    Args:
        image_path: Path to the source screenshot.
        elements: List of element dicts with 'position' (x,y) and 'size' (w,h) keys.
                  Each element should have: {'id': str, 'name': str, 'position': (x,y), 'size': (w,h)}
        output_path: Where to save the marked-up image. If None, creates a temp file.
        box_color: Hex color for bounding boxes.
        label_color: Hex color for text labels.
        box_width: Width of bounding box lines in pixels.
        font_size: Font size for element labels.

    Returns:
        Path to the saved marked-up image.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise peekxdError(
            "Pillow is required for screen markup. Install: pip install pillow"
        ) from exc

    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    # Try to load a font, fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    # Convert hex color to RGB tuple
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    rgb_box = hex_to_rgb(box_color)
    rgb_label = hex_to_rgb(label_color)

    for i, elem in enumerate(elements):
        pos = elem.get("position", (0, 0))
        size = elem.get("size", (0, 0))
        x, y = int(pos[0]), int(pos[1])
        w, h = int(size[0]), int(size[1])

        if w <= 0 or h <= 0:
            continue

        # Draw bounding box
        draw.rectangle([x, y, x + w, y + h], outline=rgb_box, width=box_width)

        # Draw label with number
        label = f"[{i}] {elem.get('name', 'elem')[:20]}"
        # Text background
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.rectangle([x, y - th - 4, x + tw + 4, y], fill=rgb_box)
        draw.text((x + 2, y - th - 2), label, fill=rgb_label, font=font)

    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), "peekxd_markup.png")

    img.save(output_path)
    return output_path


def analyze_screen_with_markup(
    image_path: str,
    prompt: Optional[str] = None,
    output_path: Optional[str] = None,
    vision_provider: Optional[Any] = None,
) -> Dict[str, Any]:
    """Analyze a screenshot and return elements with bounding boxes.

    Uses AI vision to detect all interactive UI elements and their positions.
    Returns both the element list and a marked-up image with bounding boxes.

    Args:
        image_path: Path to the screenshot to analyze.
        prompt: Custom prompt for element detection. If None, uses default.
        output_path: Where to save the marked-up image.
        vision_provider: Optional vision provider instance.

    Returns:
        Dict with keys:
            - 'elements': List of detected elements with id, name, role, position, size
            - 'markup_path': Path to the image with bounding boxes drawn
            - 'element_map': Dict mapping element indices to descriptions
    """
    from ..vision import get_vision_provider

    if vision_provider is None:
        vision_provider = get_vision_provider()

    default_prompt = (
        "Analyze this screenshot and identify ALL interactive UI elements "
        "(buttons, text fields, links, icons, menus, tabs, checkboxes, etc.). "
        "Return a JSON array of objects with these exact fields:\n"
        '[{"id": "0", "name": "Submit button", "role": "button", '
        '"position": {"x": 100, "y": 200}, "size": {"width": 80, "height": 30}}, ...]\n'
        "Include position (top-left corner) and size (width, height) in PIXELS. "
        "Be precise with coordinates. Cover the entire screen."
    )

    try:
        result = vision_provider.analyze(image_path, prompt or default_prompt)

        # Parse JSON from response
        text = result.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            text = "\n".join(lines)
            # Remove "json" language identifier if present
            if text.strip().lower().startswith("json"):
                text = text.strip()[4:].strip()

        elements_raw = json.loads(text)
        elements = []
        element_map = {}

        for i, elem in enumerate(elements_raw):
            # Normalize field names
            pos = elem.get("position", {})
            size = elem.get("size", {})

            # Handle various position formats
            if isinstance(pos, dict):
                x = pos.get("x", pos.get("left", 0))
                y = pos.get("y", pos.get("top", 0))
            elif isinstance(pos, (list, tuple)):
                x, y = pos[0], pos[1]
            else:
                x = elem.get("x", elem.get("left", 0))
                y = elem.get("y", elem.get("top", 0))

            if isinstance(size, dict):
                w = size.get("width", size.get("w", 0))
                h = size.get("height", size.get("h", 0))
            elif isinstance(size, (list, tuple)):
                w, h = size[0], size[1]
            else:
                w = elem.get("width", elem.get("w", 0))
                h = elem.get("height", elem.get("h", 0))

            normalized = {
                "id": str(i),
                "name": elem.get("name", elem.get("label", f"element_{i}")),
                "role": elem.get("role", "unknown"),
                "position": (int(x), int(y)),
                "size": (int(w), int(h)),
                "raw": elem,
            }
            elements.append(normalized)
            element_map[str(i)] = f"[{i}] {normalized['name']} ({normalized['role']}) at ({x},{y})"

        # Draw bounding boxes
        markup_path = draw_bounding_boxes(image_path, elements, output_path)

        return {
            "elements": elements,
            "markup_path": markup_path,
            "element_map": element_map,
            "count": len(elements),
        }

    except json.JSONDecodeError as exc:
        raise VisionError(f"Failed to parse element JSON from vision response: {exc}") from exc
    except Exception as exc:
        raise VisionError(f"Screen markup analysis failed: {exc}") from exc
