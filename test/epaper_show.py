#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Display a photo OR a solid color on Waveshare 7.3" e-Paper HAT (E).
# - Optional deep-clear cycles through ALL 6 Spectra colors (K,W,R,Y,B,G, then W)
# - Image mode: resizes/crops to 800x480 and quantizes to 6-color palette (dithered)
# - Solid mode: ignores image, shows a full-screen color (white/black/red/yellow/blue/green)
# - Sleeps panel after display and exits GPIO/SPI cleanly
#
# Examples:
#   # Show a photo (rotate 90 deg)
#   python3 epaper_show.py photos/cat.jpg --rotate 90
#
#   # Deep clear 1 cycle through all colors, then show a photo
#   python3 epaper_show.py photos/cat.jpg --deep-clear 1
#
#   # Just show a solid red frame (no image)
#   python3 epaper_show.py --solid red
#
#   # Two full deep-clear cycles, then show solid white
#   python3 epaper_show.py --deep-clear 2 --solid white

import sys
import argparse
import time
from pathlib import Path
from PIL import Image

# --- Import Waveshare driver ---
# Adjust search paths so this works when run from your repo or from the Waveshare example tree
_repo_lib = Path(__file__).resolve().parents[1] / "lib"
_local_ws = Path(__file__).resolve().parent / "waveshare_epd"
for _p in (str(_repo_lib), str(_local_ws)):
    if _p not in sys.path:
        sys.path.append(_p)

from waveshare_epd import epd7in3e  # type: ignore

W, H = 800, 480

# Spectra 6 palette order: White, Black, Red, Yellow, Blue, Green
PALETTE = [
    (255, 255, 255),  # white
    (0, 0, 0),        # black
    (255, 0, 0),      # red
    (255, 255, 0),    # yellow
    (0, 0, 255),      # blue
    (0, 255, 0),      # green
]

COLOR_MAP = {
    "white":  (255, 255, 255),
    "black":  (0, 0, 0),
    "red":    (255, 0, 0),
    "yellow": (255, 255, 0),
    "blue":   (0, 0, 255),
    "green":  (0, 255, 0),
}

def _build_palette_img():
    pal = Image.new("P", (1, 1))
    flat = []
    for (r, g, b) in PALETTE:
        flat += [r, g, b]
    # pad to 256 entries
    flat += [0, 0, 0] * (256 - len(PALETTE))
    pal.putpalette(flat)
    return pal

PAL_IMG = _build_palette_img()

# --- Deep clear sequence: ALL colors, end with white ---
DEEP_CLEAN_SEQUENCE = [
    (0, 0, 0),         # black
    (255, 255, 255),   # white
    (255, 0, 0),       # red
    (255, 255, 0),     # yellow
    (0, 0, 255),       # blue
    (0, 255, 0),       # green
    (255, 255, 255),   # white (final bleach)
]

def _solid_frame(epd, rgb, wait=2.0):
    """Display a solid color frame and wait for refresh to finish."""
    img = Image.new("RGB", (W, H), rgb).quantize(palette=PAL_IMG, dither=Image.NONE)
    epd.display(epd.getbuffer(img))
    time.sleep(wait)

def deep_clear(epd, cycles=1, wait=2.0):
    """Aggressive de-ghosting: sweep all Spectra colors per cycle."""
    for _ in range(cycles):
        for rgb in DEEP_CLEAN_SEQUENCE:
            _solid_frame(epd, rgb, wait)

def to_epaper_canvas(src: Image.Image, rotate: int = 0) -> Image.Image:
    """Resize/crop to 800x480 and quantize to 6-color palette (dithered)."""
    img = src.convert("RGB")
    if rotate in (90, 180, 270):
        img = img.rotate(rotate, expand=True)

    iw, ih = img.size
    target_ratio = W / H
    image_ratio = iw / ih

    if image_ratio > target_ratio:
        # wider than display ratio -> scale to height, center/crop width
        scale = H / ih
        nw, nh = int(iw * scale), H
        x = (nw - W) // 2
        img = img.resize((nw, nh), Image.LANCZOS).crop((x, 0, x + W, H))
    else:
        # taller than display ratio -> scale to width, center/crop height
        scale = W / iw
        nw, nh = W, int(ih * scale)
        y = (nh - H) // 2
        img = img.resize((nw, nh), Image.LANCZOS).crop((0, y, W, y + H))

    return img.quantize(palette=PAL_IMG, dither=Image.FLOYDSTEINBERG)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", help="Path to source image (jpg/png/etc.)")
    ap.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0,
                    help="Rotate image before placing onto canvas (image mode only)")
    ap.add_argument("--deep-clear", type=int, default=0,
                    help="Run N deep-clear cycles (K,W,R,Y,B,G,W) before output")
    ap.add_argument("--clear-wait", type=float, default=2.0,
                    help="Seconds to wait after each deep-clear frame (default: 2.0)")
    ap.add_argument("--solid", choices=list(COLOR_MAP.keys()),
                    help="Ignore image and render a solid frame: white|black|red|yellow|blue|green")
    args = ap.parse_args()

    # Validate inputs
    if not args.solid and not args.image:
        ap.error("Provide an image OR use --solid <color>")

    epd = None
    try:
        epd = epd7in3e.EPD()
        epd.init()

        # Optional: aggressive clean
        if args.deep_clear > 0:
            print(f"[epaper] Deep clear: {args.deep_clear} cycle(s) over all colors…")
            deep_clear(epd, cycles=args.deep_clear, wait=args.clear_wait)
            epd.init()  # re-init after heavy cycling

        if args.solid:
            # Solid color mode
            rgb = COLOR_MAP[args.solid]
            print(f"[epaper] Solid frame: {args.solid}")
            _solid_frame(epd, rgb, wait=2.0)

        else:
            # Image mode
            src_path = Path(args.image)
            if not src_path.exists():
                print(f"[epaper] File not found: {src_path}")
                sys.exit(1)

            # Optional light white frame helps neutralize minor tint
            _solid_frame(epd, (255, 255, 255), wait=1.0)
            epd.init()

            with Image.open(src_path) as src:
                img = to_epaper_canvas(src, rotate=args.rotate)
            print(f"[epaper] Displaying: {src_path.name}")
            epd.display(epd.getbuffer(img))
            time.sleep(2.0)

        # Done
        epd.sleep()
        epd7in3e.epdconfig.module_exit()

    except KeyboardInterrupt:
        try:
            epd7in3e.epdconfig.module_exit()
        except Exception:
            pass
    except Exception as e:
        print("[epaper] Error:", e)
        try:
            epd7in3e.epdconfig.module_exit()
        except Exception:
            pass

if __name__ == "__main__":
    main()