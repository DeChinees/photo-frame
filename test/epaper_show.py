#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Display a photo on Waveshare 7.3" e-Paper HAT (E).
# - Resizes/letterboxes to 800x480
# - Quantizes to Spectra-6 palette (W,K,R,Y,B,G) with dithering
# - Optional deep-clear (multi-color wipe) to reduce ghosting
# - Full refresh, then sleeps the panel
#
# Usage:
#   python3 epaper_show.py /path/to/photo.jpg
#
# Optional:
#   python3 epaper_show.py /path/to/photo.jpg --rotate 0|90|180|270 --deep-clear 1

import sys, argparse, time
from pathlib import Path
from PIL import Image

# Import Waveshare driver
dir_epd = str(Path(__file__).resolve().parents[1] / "lib")
if dir_epd not in sys.path:
    sys.path.append(dir_epd)

from waveshare_epd import epd7in3e

W, H = 800, 480

# Spectra 6 palette order: White, Black, Red, Yellow, Blue, Green
PALETTE = [
    (255,255,255), (0,0,0),
    (255,0,0), (255,255,0),
    (0,0,255), (0,255,0),
]

def build_palette_image():
    pal = Image.new("P", (1,1))
    table = []
    for (r,g,b) in PALETTE:
        table += [r,g,b]
    table += [0,0,0] * (256 - len(PALETTE))  # pad to 256 entries
    pal.putpalette(table)
    return pal

PAL_IMG = build_palette_image()

# Frames used for deep clear (black → white → red → white)
DEEP_CLEAN_CYCLE = [(0,0,0), (255,255,255), (255,0,0), (255,255,255)]

def _solid_frame(epd, rgb, wait=2.0):
    """Display a solid color frame and wait for refresh to finish."""
    img = Image.new("RGB", (W, H), rgb).quantize(palette=PAL_IMG, dither=Image.NONE)
    epd.display(epd.getbuffer(img))
    time.sleep(wait)

def deep_clear(epd, cycles=1, wait=2.0):
    """Run several solid color frames to aggressively reduce ghosting."""
    for _ in range(cycles):
        for rgb in DEEP_CLEAN_CYCLE:
            _solid_frame(epd, rgb, wait)

def to_epaper_canvas(src: Image.Image, rotate: int = 0) -> Image.Image:
    """Return an 800x480 Image in our 6-color palette, filling the screen."""
    img = src.convert("RGB")
    if rotate in (90,180,270):
        img = img.rotate(rotate, expand=True)

    iw, ih = img.size
    target_ratio = W / H
    image_ratio = iw / ih

    if image_ratio > target_ratio:
        # Image is wider than display ratio -> scale to height
        scale = H / ih
        nw, nh = int(iw * scale), H
        x = (nw - W) // 2
        y = 0
        img = img.resize((nw, nh), Image.LANCZOS)
        img = img.crop((x, y, x + W, y + H))
    else:
        # Image is taller -> scale to width
        scale = W / iw
        nw, nh = W, int(ih * scale)
        x = 0
        y = (nh - H) // 2
        img = img.resize((nw, nh), Image.LANCZOS)
        img = img.crop((x, y, x + W, y + H))

    # Dither into fixed 6-color palette
    return img.quantize(palette=PAL_IMG, dither=Image.FLOYDSTEINBERG)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="Path to source image (jpg/png/etc.)")
    ap.add_argument("--rotate", type=int, choices=[0,90,180,270], default=0,
                    help="Rotate before placing onto canvas")
    ap.add_argument("--deep-clear", type=int, default=0,
                    help="Run N deep-clear cycles (K→W→R→W) before showing the image")
    args = ap.parse_args()

    src_path = Path(args.image)
    if not src_path.exists():
        print(f"File not found: {src_path}")
        sys.exit(1)

    try:
        epd = epd7in3e.EPD()
        epd.init()

        if args.deep_clear > 0:
            print(f"Running deep clear ({args.deep_clear} cycle(s))...")
            deep_clear(epd, cycles=args.deep_clear, wait=2.0)
            epd.init()  # reinit after heavy cycling
        else:
            # Light clear: Clear + solid white
            try:
                epd.Clear()
                time.sleep(1.0)
            except Exception:
                pass
            _solid_frame(epd, (255,255,255), wait=1.5)
            epd.init()

        # Prepare and display image
        src = Image.open(src_path)
        img = to_epaper_canvas(src, rotate=args.rotate)
        epd.display(epd.getbuffer(img))

        time.sleep(2)  # give it time to finish

        epd.sleep()
        epd7in3e.epdconfig.module_exit()

    except KeyboardInterrupt:
        epd7in3e.epdconfig.module_exit()
    except Exception as e:
        print("Error:", e)
        epd7in3e.epdconfig.module_exit()

if __name__ == "__main__":
    main()