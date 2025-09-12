#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Display a photo on Waveshare 7.3" e-Paper HAT (E).
# - Resizes/letterboxes to 800x480
# - Quantizes to Spectra-6 palette (W,K,R,Y,B,G) with dithering
# - **Full refresh (clear to white) before displaying the new image**
# - Sleeps the panel after display
#
# Usage:
#   python3 epaper_show.py /path/to/photo.jpg
#
# Optional:
#   python3 epaper_show.py /path/to/photo.jpg --rotate 0|90|180|270 [--no-full]

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
    # pad to 256 entries
    table += [0,0,0] * (256 - len(PALETTE))
    pal.putpalette(table)
    return pal

PAL_IMG = build_palette_image()

def to_epaper_canvas(src: Image.Image, rotate: int = 0) -> Image.Image:
    """Return an 800x480 Image in our 6-color palette, filling the screen."""
    img = src.convert("RGB")
    if rotate in (90,180,270):
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

    # Dither into fixed 6-color palette
    return img.quantize(palette=PAL_IMG, dither=Image.FLOYDSTEINBERG)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="Path to source image (jpg/png/etc.)")
    ap.add_argument("--rotate", type=int, choices=[0,90,180,270], default=0,
                    help="Rotate before placing onto canvas")
    ap.add_argument("--no-full", action="store_true",
                    help="Skip the full white refresh before displaying")
    args = ap.parse_args()

    src_path = Path(args.image)
    if not src_path.exists():
        print(f"File not found: {src_path}")
        sys.exit(1)

    epd = None
    try:
        epd = epd7in3e.EPD()
        epd.init()

        if not args.no_full:
            # Full panel clear to white (driver default color is white for this panel)
            epd.Clear()
            # Give the panel a moment to settle
            time.sleep(1.0)
            # Some Waveshare drivers need re-init after a Clear()
            epd.init()

        # Prepare and display image
        src = Image.open(src_path)
        img = to_epaper_canvas(src, rotate=args.rotate)
        epd.display(epd.getbuffer(img))

        # Ensure refresh has time to complete
        time.sleep(2.0)

        # Put panel to sleep (image remains)
        epd.sleep()

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("Error:", e)
    finally:
        # Always exit the SPI/GPIO module cleanly
        try:
            epd7in3e.epdconfig.module_exit()
        except Exception:
            pass

if __name__ == "__main__":
    main()