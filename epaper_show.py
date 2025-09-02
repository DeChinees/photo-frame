#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Display a photo on Waveshare 7.3" e-Paper HAT (E).
# - Resizes/letterboxes to 800x480
# - Quantizes to Spectra-6 palette (W,K,R,Y,B,G) with dithering
# - Full refresh, then sleeps the panel
#
# Usage:
#   python3 epaper_show.py /path/to/photo.jpg
#
# Optional:
#   python3 epaper_show.py /path/to/photo.jpg --rotate 0|90|180|270

import sys, argparse, time
from pathlib import Path
from PIL import Image

# Import Waveshare driver
# Make sure you run this from inside the Waveshare examples directory OR
# that the 'lib' folder is on sys.path.
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
    # pad to 256 entries
    table += [0,0,0] * (256 - len(PALETTE))
    pal.putpalette(table)
    return pal

PAL_IMG = build_palette_image()

def to_epaper_canvas(src: Image.Image, rotate: int = 0) -> Image.Image:
    """Return an 800x480, dithered Image in our 6-color palette."""
    img = src.convert("RGB")
    if rotate in (90,180,270):
        img = img.rotate(rotate, expand=True)

    iw, ih = img.size
    scale = min(W/iw, H/ih)
    nw, nh = max(1, int(iw*scale)), max(1, int(ih*scale))
    img = img.resize((nw, nh), Image.LANCZOS)

    canvas = Image.new("RGB", (W, H), (255,255,255))
    canvas.paste(img, ((W - nw)//2, (H - nh)//2))

    # Dither into fixed 6-color palette
    q = canvas.quantize(palette=PAL_IMG, dither=Image.FLOYDSTEINBERG)
    # Waveshare driver expects mode 'P' or 'RGB' depending on panel; their 7in3e
    # driver handles color-indexed input via getbuffer().
    return q

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="Path to source image (jpg/png/etc.)")
    ap.add_argument("--rotate", type=int, choices=[0,90,180,270], default=0,
                    help="Rotate before placing onto canvas")
    args = ap.parse_args()

    src_path = Path(args.image)
    if not src_path.exists():
        print(f"File not found: {src_path}")
        sys.exit(1)

    try:
        epd = epd7in3e.EPD()
        epd.init()                      # Changed from Init() to init()
        # If you see ghosting, you can epd.Clear() once on first use (slow).
        # epd.clear()                   # Also lowercase if needed

        # Prepare image
        src = Image.open(src_path)
        img = to_epaper_canvas(src, rotate=args.rotate)

        # Display
        # Waveshare's getbuffer() converts the PIL image to the panel's buffer format.
        epd.display(epd.getbuffer(img))

        # Give it time to complete the refresh (driver waits for BUSY; this is extra guard)
        time.sleep(2)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("Error:", e)
    finally:
        try:
            # Put panel to sleep (extremely low power; image remains)
            epd.sleep()
        except Exception:
            pass

if __name__ == "__main__":
    main()