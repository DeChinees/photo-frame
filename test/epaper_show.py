#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import argparse
import time
from pathlib import Path
from PIL import Image

# --- Import Waveshare driver ---
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
    flat += [0, 0, 0] * (256 - len(PALETTE))
    pal.putpalette(flat)
    return pal

PAL_IMG = _build_palette_img()

# Deep-clear over ALL colors, end on white
DEEP_CLEAN_SEQUENCE = [
    (0, 0, 0),         # black
    (255, 255, 255),   # white
    (255, 0, 0),       # red
    (255, 255, 0),     # yellow
    (0, 0, 255),       # blue
    (0, 255, 0),       # green
    (255, 255, 255),   # white (final)
]

def _solid_frame(epd, rgb, wait=2.0):
    img = Image.new("RGB", (W, H), rgb).quantize(palette=PAL_IMG, dither=Image.NONE)
    epd.display(epd.getbuffer(img))
    time.sleep(wait)

def deep_clear(epd, cycles=1, wait=2.0):
    for _ in range(cycles):
        for rgb in DEEP_CLEAN_SEQUENCE:
            _solid_frame(epd, rgb, wait)

def to_epaper_canvas(src: Image.Image, rotate: int = 0) -> Image.Image:
    img = src.convert("RGB")
    if rotate in (90, 180, 270):
        img = img.rotate(rotate, expand=True)

    iw, ih = img.size
    target_ratio = W / H
    image_ratio = iw / ih

    if image_ratio > target_ratio:
        scale = H / ih
        nw, nh = int(iw * scale), H
        x = (nw - W) // 2
        img = img.resize((nw, nh), Image.LANCZOS).crop((x, 0, x + W, H))
    else:
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

    # NEW: allow deep-clear only; error only if nothing at all was requested
    if not args.solid and not args.image and args.deep_clear == 0:
        ap.error("Provide an image OR --solid <color> OR --deep-clear N")

    epd = None
    try:
        epd = epd7in3e.EPD()
        epd.init()

        # Optional deep-clear first
        if args.deep_clear > 0:
            print(f"[epaper] Deep clear: {args.deep_clear} cycle(s) over all colors…")
            deep_clear(epd, cycles=args.deep_clear, wait=args.clear_wait)
            epd.init()  # re-init after heavy cycling

        if args.solid:
            # Solid color mode
            rgb = COLOR_MAP[args.solid]
            print(f"[epaper] Solid frame: {args.solid}")
            _solid_frame(epd, rgb, wait=2.0)

        elif args.image:
            # Image mode
            src_path = Path(args.image)
            if not src_path.exists():
                print(f"[epaper] File not found: {src_path}")
                sys.exit(1)

            # Light pre-bleach to white
            _solid_frame(epd, (255, 255, 255), wait=1.0)
            epd.init()

            with Image.open(src_path) as src:
                img = to_epaper_canvas(src, rotate=args.rotate)
            print(f"[epaper] Displaying: {src_path.name}")
            epd.display(epd.getbuffer(img))
            time.sleep(2.0)

        else:
            # Deep-clear only case (no image/solid): end on white
            print("[epaper] Deep-clear only; leaving panel white.")
            _solid_frame(epd, (255, 255, 255), wait=1.0)

        epd.sleep()
        epd7in3e.epdconfig.module_exit()

    except KeyboardInterrupt:
        try: epd7in3e.epdconfig.module_exit()
        except Exception: pass
    except Exception as e:
        print("[epaper] Error:", e)
        try: epd7in3e.epdconfig.module_exit()
        except Exception: pass

if __name__ == "__main__":
    main()