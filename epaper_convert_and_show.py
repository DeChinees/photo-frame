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
    
    # Determine orientation of both target display and input image
    target_is_landscape = target_w > target_h
    image_is_landscape = iw > ih
    
    # Rotate image 90 degrees if orientations don't match
    if target_is_landscape != image_is_landscape:
        img = img.rotate(90, expand=True)
        iw, ih = ih, iw  # Update dimensions after rotation
    
    # Calculate scaling while preserving aspect ratio
    scale = min(target_w/iw, target_h/ih)
    nw, nh = max(1, int(iw*scale)), max(1, int(ih*scale))
    
    # Resize image maintaining aspect ratio
    img = img.resize((nw, nh), Image.LANCZOS)
    
    # Create white canvas with target dimensions
    canvas = Image.new("RGB", (target_w, target_h), (255,255,255))
    
    # Center the image on canvas
    x_offset = (target_w - nw) // 2
    y_offset = (target_h - nh) // 2
    canvas.paste(img, (x_offset, y_offset))
    
    # Quantize to palette colors
    q = canvas.quantize(palette=palimg, dither=Image.FLOYDSTEINBERG)
    q.save(out_path)

def cleanup():
    """Restore cursor and terminal settings"""
    subprocess.run(["setterm", "-cursor", "on", "-term", "linux"], check=False)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Convert only: epaper_convert_and_show.py <input_image>")
        print("  Convert and display: epaper_convert_and_show.py <input_image> [fbdev] [tty]")
        print("Example:")
        print("  epaper_convert_and_show.py ~/photo.jpg")
        print("  epaper_convert_and_show.py ~/photo.jpg /dev/fb0 1")
        sys.exit(1)

    src = sys.argv[1]
    # Get output filename based on input
    out = Path(src).with_suffix('.converted.png')
    
    if len(sys.argv) == 2:
        # Convert only mode
        w, h = 800, 480  # Default resolution
        convert_to_palette(src, out, w, h)
        print(f"Converted image saved to: {out}")
    else:
        try:
            # Convert and display mode
            fbdev = sys.argv[2] if len(sys.argv) > 2 else "/dev/fb0"
            tty = sys.argv[3] if len(sys.argv) > 3 else "1"

            w, h = read_fb_resolution(fbdev)
            temp_out = "/tmp/epaper_preview.png"
            convert_to_palette(src, temp_out, w, h)

            # show on the specified framebuffer TTY
            try:
                subprocess.run(["chvt", str(tty)], check=False)
            except Exception:
                pass
            subprocess.run(["setterm","-cursor","off","-term","linux","-foreground","white","-clear","all"], check=False)
            subprocess.run(["sudo","fbi","-T", str(tty), "-d", fbdev, "--noverbose", "-a", temp_out])
        finally:
            cleanup()

if __name__ == "__main__":
    main()
