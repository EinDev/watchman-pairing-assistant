"""
One-off script used to generate the device-row icons:
resources/icon_hmd_light.png, icon_hmd_dark.png,
resources/icon_controller_light.png, icon_controller_dark.png.

Small, flat, single-color glyphs on a transparent background. Each icon is
rendered once per appearance mode, using the same text colors the rest of
the app already uses (see DeviceFrame's text_color=("#696969", "#DCE4EE")),
so contrast stays good against the device row background in both modes.
Re-run this script to regenerate the PNGs if the glyphs ever need to change.

Usage: python resources/generate_icons.py
"""
import os
from PIL import Image, ImageDraw

SIZE = 48
GLYPH_COLORS = {
    "light": (0x69, 0x69, 0x69, 255),  # matches text_color light-mode value #696969
    "dark": (0xDC, 0xE4, 0xEE, 255),   # matches text_color dark-mode value #DCE4EE
}
CUTOUT_COLOR = (0, 0, 0, 0)
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _new_canvas():
    return Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))


def draw_hmd_icon(glyph_color):
    """VR-headset glyph, front-on: a solid visor body with short strap tabs on
    the sides. No lens cut-outs (circles read as eyes/a face at this size)
    and no rotation (blurs badly on a shape this simple at 20px)."""
    scale = 4  # supersample for clean anti-aliased edges, then downsample
    def pt(x, y):
        return (x * scale, y * scale)

    img = Image.new("RGBA", (SIZE * scale, SIZE * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Strap tabs poking out from the sides, suggesting the head strap
    draw.rounded_rectangle([*pt(0, 20), *pt(10, 28)], radius=3 * scale, fill=glyph_color)
    draw.rounded_rectangle([*pt(38, 20), *pt(48, 28)], radius=3 * scale, fill=glyph_color)

    # Visor / front panel
    draw.rounded_rectangle([*pt(9, 12), *pt(39, 36)], radius=8 * scale, fill=glyph_color)

    return img.resize((SIZE, SIZE), Image.LANCZOS)


def draw_controller_icon(glyph_color):
    """Simple game-controller glyph: rounded body with two grip bumps and face buttons."""
    img = _new_canvas()
    draw = ImageDraw.Draw(img)

    # Main body
    draw.rounded_rectangle((4, 16, 44, 32), radius=10, fill=glyph_color)

    # Left grip
    draw.ellipse((2, 24, 14, 40), fill=glyph_color)
    # Right grip
    draw.ellipse((34, 24, 46, 40), fill=glyph_color)

    # D-pad (transparent cut-out, left side)
    draw.rectangle((11, 21, 15, 29), fill=CUTOUT_COLOR)
    draw.rectangle((8, 24, 18, 26), fill=CUTOUT_COLOR)

    # Face buttons (transparent cut-outs, right side)
    draw.ellipse((30, 19, 34, 23), fill=CUTOUT_COLOR)
    draw.ellipse((36, 22, 40, 26), fill=CUTOUT_COLOR)

    return img


def main():
    for mode, color in GLYPH_COLORS.items():
        hmd_path = os.path.join(OUT_DIR, f"icon_hmd_{mode}.png")
        controller_path = os.path.join(OUT_DIR, f"icon_controller_{mode}.png")

        draw_hmd_icon(color).save(hmd_path)
        draw_controller_icon(color).save(controller_path)

        print(f"Wrote {hmd_path}")
        print(f"Wrote {controller_path}")


if __name__ == "__main__":
    main()
