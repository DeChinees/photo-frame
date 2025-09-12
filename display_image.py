#!/usr/bin/env python3
"""
Display the symlinked image on the e-paper, then rotate 'current' to the next.
Designed for Waveshare 7.3" e-Paper HAT (E).

Run this periodically (cron / systemd timer) to advance the slideshow.
"""

import sys
import time
import fcntl
from pathlib import Path

# --- Paths & panel config ---
BASE = Path(__file__).resolve().parent
PHOTOS = BASE / "photos"
READY_DIR = PHOTOS / "photos_ready"
LINK_PATH = PHOTOS / "current.bmp"

EPAPER_WIDTH = 800
EPAPER_HEIGHT = 480

# --- Optional: local waveshare lib (if you vendored it in the repo) ---
from waveshare_epd import epd7in3e
try:
    from waveshare_epd import epd7in3e
except ImportError:
    # If you keep waveshare_epd inside the repo, uncomment these lines:
    sys.path.append(str(BASE / "waveshare_epd"))
    from epd7in3e import EPD
    print("Error: waveshare_epd not found. Install per Waveshare's wiki or vendor it in the repo.")
    sys.exit(1)

from PIL import Image

LOCKFILE = PHOTOS / ".display.lock"


def log(msg: str):
    print(f"[display_next] {msg}", flush=True)


def acquire_lock():
    LOCKFILE.parent.mkdir(parents=True, exist_ok=True)
    f = open(LOCKFILE, "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except BlockingIOError:
        log("another instance is running; exiting")
        f.close()
        sys.exit(0)


def list_ready_names():
    return sorted(p.name for p in READY_DIR.glob("*.bmp"))


def resolve_current():
    if not LINK_PATH.exists():
        return None
    if not LINK_PATH.is_symlink():
        # be tolerant: if it's a real file, use it as-is but don’t rotate.
        return LINK_PATH
    try:
        return LINK_PATH.resolve()
    except Exception:
        return None


def atomic_point_current(to_path: Path):
    tmp = LINK_PATH.with_suffix(".tmp")
    try:
        tmp.unlink(missing_ok=True)
        tmp.symlink_to(to_path)
        tmp.replace(LINK_PATH)
    except Exception as e:
        log(f"failed to repoint symlink: {e}")


def pick_next_after(current_path: Path | None, ready_list: list[str]) -> Path | None:
    """Given current (may be None), return the NEXT path (wrap), or first if none."""
    if not ready_list:
        return None
    if current_path is None:
        return READY_DIR / ready_list[0]
    try:
        idx = ready_list.index(current_path.name)
    except ValueError:
        # current not in list; pick first
        return READY_DIR / ready_list[0]
    nxt = ready_list[(idx + 1) % len(ready_list)]
    return READY_DIR / nxt


def open_as_panel_image(p: Path) -> Image.Image:
    """Open BMP and ensure it is exactly EPAPER_WIDTH x EPAPER_HEIGHT."""
    img = Image.open(p)
    if img.size != (EPAPER_WIDTH, EPAPER_HEIGHT):
        log(f"warning: {p.name} is {img.size}, resizing to {(EPAPER_WIDTH, EPAPER_HEIGHT)}")
        img = img.convert("RGB").resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
    # The file you prepared is palettized BMP already; epd.getbuffer() accepts PIL Image.
    return img


def render_to_epaper(img: Image.Image):
    # Initialize panel, display, sleep
    epd = epd7in3e.EPD()
    epd.init()  # NOTE: lowercase 'init' for epd7in3e lib
    try:
        buf = epd.getbuffer(img)
        epd.display(buf)
        # Give panel a moment to settle before sleeping
        time.sleep(1.0)
    finally:
        try:
            epd.sleep()
        except Exception:
            pass


def main():
    lock = acquire_lock()
    try:
        READY_DIR.mkdir(parents=True, exist_ok=True)

        ready = list_ready_names()
        if not ready:
            log("no prepared images in photos/photos_ready — nothing to display")
            return

        current_path = resolve_current()
        if current_path is None or not current_path.exists():
            log("current symlink missing/broken; selecting first image")
            current_path = READY_DIR / ready[0]
            atomic_point_current(current_path)

        # Display current
        log(f"displaying: {current_path.name}")
        img = open_as_panel_image(current_path)
        render_to_epaper(img)

        # Rotate current -> next
        next_path = pick_next_after(current_path, ready)
        if next_path and next_path != current_path:
            atomic_point_current(next_path)
            log(f"rotated next: {next_path.name}")
        else:
            log("only one image in list; staying on current")

    finally:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()