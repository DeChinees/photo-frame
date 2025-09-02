#!/usr/bin/env python3
import sys, os, subprocess
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter

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

def apply_lcd_effect(image):
    """Apply LCD display simulation effects"""
    # Enhance contrast slightly
    contrast = ImageEnhance.Contrast(image)
    image = contrast.enhance(1.2)
    
    # Add slight sharpness
    sharpness = ImageEnhance.Sharpness(image)
    image = sharpness.enhance(1.1)
    
    # Slightly increase brightness
    brightness = ImageEnhance.Brightness(image)
    image = brightness.enhance(1.1)
    
    return image

def convert_to_palette(src_path, out_path, target_w, target_h, display_type='normal'):
    palimg = build_palette_image()
    img = Image.open(src_path).convert("RGB")
    
    # Apply display simulation effects
    if display_type == 'lcd':
        img = apply_lcd_effect(img)
    
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

def resize_and_center(img, target_w, target_h):
    """Resize and center image without palette conversion"""
    iw, ih = img.size
    
    # Determine orientation
    target_is_landscape = target_w > target_h
    image_is_landscape = iw > ih
    
    # Rotate if needed
    if target_is_landscape != image_is_landscape:
        img = img.rotate(90, expand=True)
        iw, ih = ih, iw
    
    # Calculate scaling
    scale = min(target_w/iw, target_h/ih)
    nw, nh = max(1, int(iw*scale)), max(1, int(ih*scale))
    
    # Resize
    img = img.resize((nw, nh), Image.LANCZOS)
    
    # Center on white canvas
    canvas = Image.new("RGB", (target_w, target_h), (255,255,255))
    x_offset = (target_w - nw) // 2
    y_offset = (target_h - nh) // 2
    canvas.paste(img, (x_offset, y_offset))
    
    return canvas

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Convert: epaper_convert_and_show.py <input_image>")
        print("  Raw display: epaper_convert_and_show.py <input_image> [fbdev] [tty] --raw")
        print("Example:")
        print("  epaper_convert_and_show.py ~/photo.jpg")
        print("  epaper_convert_and_show.py ~/photo.jpg /dev/fb0 1 --raw")
        sys.exit(1)

    src = sys.argv[1]
    is_raw = '--raw' in sys.argv
    out = Path(src).with_suffix('.converted.png')
    
    if len(sys.argv) == 2:
        # Convert only mode
        w, h = 800, 480
        convert_to_palette(src, out, w, h)
        print(f"Converted image saved to: {out}")
    else:
        try:
            # Display mode
            args = [arg for arg in sys.argv[2:] if not arg.startswith('--')]
            fbdev = args[0] if args else "/dev/fb0"
            tty = args[1] if len(args) > 1 else "1"

            w, h = read_fb_resolution(fbdev)
            temp_out = "/tmp/epaper_preview.png"
            
            if is_raw:
                # Raw display without palette conversion
                img = Image.open(src).convert("RGB")
                resized = resize_and_center(img, w, h)
                resized.save(temp_out)
            else:
                # Normal palette conversion
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
