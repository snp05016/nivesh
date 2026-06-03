#!/usr/bin/env python3
"""
Generate Nivesh app icons for iOS.
Design: dark charcoal background, gold double border, large "N" with gradient,
rising chart line, and "निवेश" subtitle.
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = "/Users/saumya/Desktop/stockapp-ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset"
SIZES = [20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180, 1024]

BG_COLOR = (28, 26, 20)          # #1C1A14
GOLD = (200, 168, 74)             # #C8A84A
GOLD_DARK = (184, 151, 58)        # #B8973A

GEORGIA_BOLD = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
GEORGIA_ITALIC = "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"
GEORGIA = "/System/Library/Fonts/Supplemental/Georgia.ttf"


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def make_rounded_mask(size, radius):
    """Create a rounded rectangle mask."""
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def draw_gradient_text(draw, img, text, font, x, y, color_top, color_bottom):
    """Draw text with a vertical gradient by compositing."""
    # Create text layer
    txt_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_layer)
    txt_draw.text((x, y), text, font=font, fill=(255, 255, 255, 255), anchor="mm")

    # Create gradient layer matching text bounding box
    bbox = font.getbbox(text)
    text_h = bbox[3] - bbox[1]
    text_w = bbox[2] - bbox[0]
    half_h = text_h // 2 + 2

    grad = Image.new('RGBA', img.size, (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)

    # Vertical gradient from color_top to color_bottom over the text height
    for row in range(int(y - half_h), int(y + half_h) + 1):
        if 0 <= row < img.size[1]:
            t = (row - (y - half_h)) / max(text_h, 1)
            t = max(0.0, min(1.0, t))
            r = int(color_top[0] + t * (color_bottom[0] - color_top[0]))
            g = int(color_top[1] + t * (color_bottom[1] - color_top[1]))
            b = int(color_top[2] + t * (color_bottom[2] - color_top[2]))
            grad_draw.line([(0, row), (img.size[0], row)], fill=(r, g, b, 255))

    # Use text as mask to apply gradient
    colored = Image.composite(grad, Image.new('RGBA', img.size, (0, 0, 0, 0)), txt_layer.split()[3])
    return colored


def generate_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Background (filled rounded rect) ---
    corner_radius = int(size * 0.22)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=corner_radius, fill=BG_COLOR + (255,))

    # --- Double border ---
    # Outer border: gold, 1.5px equivalent, opacity 0.5
    outer_alpha = int(255 * 0.5)
    outer_color = GOLD + (outer_alpha,)
    border_w_outer = max(1, int(size * 0.015))
    half_outer = border_w_outer / 2
    draw.rounded_rectangle(
        [half_outer, half_outer, size - 1 - half_outer, size - 1 - half_outer],
        radius=corner_radius - int(half_outer),
        outline=outer_color,
        width=border_w_outer
    )

    # Inner border: gold, 0.5px, opacity 0.25, inset 4px scaled
    inner_inset = max(2, int(size * 0.04))
    inner_alpha = int(255 * 0.25)
    inner_color = GOLD + (inner_alpha,)
    inner_radius = max(1, corner_radius - inner_inset)
    draw.rounded_rectangle(
        [inner_inset, inner_inset, size - 1 - inner_inset, size - 1 - inner_inset],
        radius=inner_radius,
        outline=inner_color,
        width=max(1, int(size * 0.005))
    )

    # --- Rising chart polyline (behind N) ---
    chart_alpha = int(255 * 0.6)
    chart_color = GOLD + (chart_alpha,)

    # Chart goes from bottom-left area to top-right area
    margin = size * 0.18
    chart_points = [
        (size * 0.15, size * 0.80),
        (size * 0.28, size * 0.68),
        (size * 0.40, size * 0.72),
        (size * 0.52, size * 0.58),
        (size * 0.65, size * 0.48),
        (size * 0.78, size * 0.32),
        (size * 0.85, size * 0.22),
    ]
    chart_points = [(int(x), int(y)) for x, y in chart_points]
    line_width = max(1, int(size * 0.018))
    draw.line(chart_points, fill=chart_color, width=line_width, joint="curve")

    # Dot at the top-right end of chart line
    dot_x, dot_y = chart_points[-1]
    dot_r = max(2, int(size * 0.035))
    draw.ellipse(
        [dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r],
        fill=GOLD + (255,)
    )

    # --- "N" letterform with gradient ---
    n_size = int(size * 0.60)
    try:
        n_font = ImageFont.truetype(GEORGIA_BOLD, n_size)
    except Exception:
        try:
            n_font = ImageFont.truetype(GEORGIA, n_size)
        except Exception:
            n_font = ImageFont.load_default()

    center_x = size // 2
    # Shift N slightly up to leave room for subtitle
    center_y = int(size * 0.46)

    gradient_layer = draw_gradient_text(
        draw, img, "N", n_font, center_x, center_y, GOLD, GOLD_DARK
    )
    img = Image.alpha_composite(img, gradient_layer)

    # --- "निवेश" subtitle ---
    if size >= 40:
        sub_size = max(8, int(size * 0.10))
        try:
            sub_font = ImageFont.truetype(GEORGIA_ITALIC, sub_size)
        except Exception:
            try:
                sub_font = ImageFont.truetype(GEORGIA, sub_size)
            except Exception:
                sub_font = ImageFont.load_default()

        sub_alpha = int(255 * 0.65)
        sub_color = GOLD + (sub_alpha,)
        sub_draw = ImageDraw.Draw(img)
        sub_y = int(size * 0.80)
        sub_draw.text((center_x, sub_y), "निवेश", font=sub_font, fill=sub_color, anchor="mm")

    # --- Apply rounded corner mask ---
    mask = make_rounded_mask(size, corner_radius)
    img.putalpha(mask)

    # Convert to RGB with dark background for PNG (iOS expects no transparency in app icons)
    final = Image.new('RGB', (size, size), BG_COLOR)
    final.paste(img, mask=img.split()[3])

    return final


def generate_all():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    generated = []

    for size in SIZES:
        try:
            icon = generate_icon(size)
            filename = f"Icon-{size}.png"
            filepath = os.path.join(OUTPUT_DIR, filename)
            icon.save(filepath, 'PNG', optimize=True)
            generated.append((size, filename))
            print(f"  Generated {filename} ({size}x{size})")
        except Exception as e:
            print(f"  ERROR generating {size}px: {e}")
            import traceback; traceback.print_exc()

    return generated


def update_contents_json(generated):
    import json

    # Map sizes to their iOS icon slot metadata
    # Format: (size_pt, scale, idiom, platform)
    ios_slots = [
        # iOS universal (required sizes for modern Xcode)
        {"filename": "Icon-1024.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"},
        # Notification
        {"filename": "Icon-40.png",  "idiom": "iphone", "scale": "2x", "size": "20x20"},
        {"filename": "Icon-60.png",  "idiom": "iphone", "scale": "3x", "size": "20x20"},
        {"filename": "Icon-58.png",  "idiom": "iphone", "scale": "2x", "size": "29x29"},
        {"filename": "Icon-87.png",  "idiom": "iphone", "scale": "3x", "size": "29x29"},
        {"filename": "Icon-80.png",  "idiom": "iphone", "scale": "2x", "size": "40x40"},
        {"filename": "Icon-120.png", "idiom": "iphone", "scale": "3x", "size": "40x40"},
        {"filename": "Icon-120.png", "idiom": "iphone", "scale": "2x", "size": "60x60"},
        {"filename": "Icon-180.png", "idiom": "iphone", "scale": "3x", "size": "60x60"},
        # iPad
        {"filename": "Icon-20.png",  "idiom": "ipad",   "scale": "1x", "size": "20x20"},
        {"filename": "Icon-40.png",  "idiom": "ipad",   "scale": "2x", "size": "20x20"},
        {"filename": "Icon-29.png",  "idiom": "ipad",   "scale": "1x", "size": "29x29"},
        {"filename": "Icon-58.png",  "idiom": "ipad",   "scale": "2x", "size": "29x29"},
        {"filename": "Icon-40.png",  "idiom": "ipad",   "scale": "1x", "size": "40x40"},
        {"filename": "Icon-80.png",  "idiom": "ipad",   "scale": "2x", "size": "40x40"},
        {"filename": "Icon-76.png",  "idiom": "ipad",   "scale": "1x", "size": "76x76"},
        {"filename": "Icon-152.png", "idiom": "ipad",   "scale": "2x", "size": "76x76"},
        {"filename": "Icon-167.png", "idiom": "ipad",   "scale": "2x", "size": "83.5x83.5"},
        {"filename": "Icon-1024.png","idiom": "ipad",   "scale": "2x", "size": "512x512"},
    ]

    generated_filenames = {f for _, f in generated}
    images = []

    for slot in ios_slots:
        entry = {k: v for k, v in slot.items()}
        if slot["filename"] not in generated_filenames:
            # Remove filename reference if file wasn't generated
            entry.pop("filename", None)
        images.append({k: v for k, v in entry.items() if k != "filename" or v in generated_filenames})

    # Build proper entries
    images_out = []
    for slot in ios_slots:
        entry = {}
        if slot["filename"] in generated_filenames:
            entry["filename"] = slot["filename"]
        entry["idiom"] = slot["idiom"]
        if "platform" in slot:
            entry["platform"] = slot["platform"]
        if "scale" in slot:
            entry["scale"] = slot["scale"]
        entry["size"] = slot["size"]
        images_out.append(entry)

    contents = {
        "images": images_out,
        "info": {
            "author": "xcode",
            "version": 1
        }
    }

    contents_path = os.path.join(OUTPUT_DIR, "Contents.json")
    with open(contents_path, 'w') as f:
        json.dump(contents, f, indent=2)
    print(f"\n  Updated Contents.json with {len(images_out)} entries")


if __name__ == "__main__":
    print("Generating Nivesh app icons...")
    generated = generate_all()
    print(f"\nGenerated {len(generated)} icons.")
    update_contents_json(generated)
    print("\nDone!")
