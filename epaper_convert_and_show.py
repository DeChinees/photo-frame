#!/usr/bin/env python3
import sys, os, subprocess
from pathlib import Path
from PIL import Image

# 6-color e-ink palette (W, K, R, Y, B, G)
PALETTE = [(255,255,255),(0,0,0),(255,0,0),(255,255,0),(0,0,255),(0,255,0)]

def build_palette_image():
    pal = Image.new('P', (1,1))
    flat=[]
    for r,g,b in PALETTE: flat += [r,g,b]
    flat += [0,0,0]*(256-len(PALETTE))
    pal.putpalette(flat)
    return pal

def read_fb_resolution(fbdev="/dev/fb0"):
    # Try /sys first
    sysdir = Path(f"/sys/class/graphics/{Path(fbdev).name}")
    vs = sysdir/"virtual_size"
    if vs.exists():
        w,h = (int(x) for x in vs.read_text().strip().split(","))
        if w>0 and h>0:
            return w,h
    # Fallback: fbset -s
    try:
        out = subprocess.check_output(["fbset","-s"], text=True, stderr=subprocess.DEVNULL)
        # line like: "geometry 1920 1080 1920 1080 32"
        for line in out.splitlines():
            if "geometry" in line:
                parts = line.split()
                return int(parts[1]), int(parts[2])
    except Exception:
        pass
    # Last resort
    return 800,480

def convert_to_palette(src_path, out_path, target_w, target_h):
    palimg = build_palette_image()
    img = Image.open(src_path).convert("RGB")
    iw, ih = img.size
    scale = min(target_w/iw, target_h/ih)
    nw, nh = max(1,int(iw*scale)), max(1,int(ih*scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), (255,255,255))
    canvas.paste(img, ((target_w-nw)//2, (target_h-nh)//2))
    q = canvas.quantize(palette=palimg, dither=Image.FLOYDSTEINBERG)
    q.save(out_path)

def main():
    if len(sys.argv) < 2:
        print("usage: epaper_convert_and_show.py <input_image> [fbdev] [tty]")
        print("example: epaper_convert_and_show.py ~/photo.jpg /dev/fb0 1")
        sys.exit(1)
    src = sys.argv[1]
    fbdev = sys.argv[2] if len(sys.argv) > 2 else "/dev/fb0"
    tty = sys.argv[3] if len(sys.argv) > 3 else "1"

    w,h = read_fb_resolution(fbdev)
    out = "/tmp/epaper_preview.png"
    convert_to_palette(src, out, w, h)

    # show on the specified framebuffer TTY, no X needed
    # ensure we are on that tty (optional)
    try:
        subprocess.run(["chvt", str(tty)], check=False)
    except Exception:
        pass
    # hide cursor (optional)
    subprocess.run(["setterm","-cursor","off","-term","linux","-foreground","white","-clear","all"], check=False)
    # display
    subprocess.run(["sudo","fbi","-T", str(tty), "-d", fbdev, "--noverbose", "-a", out])

if __name__ == "__main__":
    main()
