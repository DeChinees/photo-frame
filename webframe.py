#!/usr/bin/env python3
import os
import logging
import subprocess
import secrets
from pathlib import Path
from datetime import datetime

from flask import (
    Flask, request, redirect, url_for,
    render_template, send_from_directory, abort
)
from werkzeug.utils import secure_filename
from PIL import Image
from logging.handlers import RotatingFileHandler

# ========================
# Config / Constants
# ========================
__version__ = "0.1.1"

BASE = Path(__file__).resolve().parent
PHOTOS_BASE = BASE / "photos"
SRC_DIR   = PHOTOS_BASE / "photos_source"
READY_DIR = PHOTOS_BASE / "photos_ready"
THUMB_DIR = PHOTOS_BASE / "thumbs"
LINK_PATH = PHOTOS_BASE / "current.bmp"

# Panel dimensions
W, H = 800, 480

# 6-color palette (Waveshare Spectra-like)
PALETTE = [
    (255, 255, 255),  # white
    (0, 0, 0),        # black
    (255, 0, 0),      # red
    (255, 255, 0),    # yellow
    (0, 0, 255),      # blue
    (0, 255, 0),      # green
]

TOKEN = os.environ.get("FRAME_TOKEN", "changeme123")
HEIC_EXTS = {".heic", ".heif"}

for p in (SRC_DIR, READY_DIR, THUMB_DIR):
    p.mkdir(parents=True, exist_ok=True)

# ========================
# Logging -> /var/log/photo-frame/web.log (1MB rotate, keep 5)
# ========================
LOG_DIR = Path("/var/log/photo-frame")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "web.log"

handler = RotatingFileHandler(LOG_FILE, maxBytes=1 * 1024 * 1024, backupCount=5)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)

root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(handler)

log = logging.getLogger("webframe")

# ========================
# Flask
# ========================
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB per request

# ========================
# Helpers
# ========================
def _palette_img():
    pal = Image.new("P", (1, 1))
    flat = []
    for r, g, b in PALETTE:
        flat += [r, g, b]
    flat += [0, 0, 0] * (256 - len(PALETTE))
    pal.putpalette(flat)
    return pal
_PAL_IMG = _palette_img()

def prepare_epaper_frame(src: Path) -> Image.Image:
    """Open, letterbox to 800x480 on white, quantize to palette."""
    img = Image.open(src).convert("RGB")
    iw, ih = img.size
    scale = min(W / iw, H / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    canvas.paste(img, ((W - nw) // 2, (H - nh) // 2))
    return canvas.quantize(palette=_PAL_IMG, dither=Image.FLOYDSTEINBERG)

def normalize_to_jpeg_if_heic(path: Path) -> Path:
    """If HEIC/HEIF, convert using heif-convert -> JPEG. Return new path."""
    if path.suffix.lower() not in HEIC_EXTS:
        return path
    jpg = path.with_suffix(".jpg")
    try:
        subprocess.run(["heif-convert", str(path), str(jpg)], check=True, capture_output=True)
        path.unlink(missing_ok=True)
        log.info("upload: heic→jpeg %s -> %s", path.name, jpg.name)
        return jpg
    except Exception as e:
        log.exception("upload: heic-convert failed for %s: %s", path.name, e)
        return path

def list_ready():
    return sorted([p.name for p in READY_DIR.glob("*.bmp")])

def set_symlink(ready_name: str):
    """Point photos/current.bmp at photos_ready/<ready_name> (atomic-ish)."""
    target = READY_DIR / ready_name
    if not target.exists():
        raise FileNotFoundError(target)
    tmp = LINK_PATH.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(target)          # create the symlink file
    tmp.replace(LINK_PATH)          # atomic rename

def require_token(req):
    t = req.form.get("token") or req.args.get("token") or req.headers.get("X-Auth-Token")
    if t != TOKEN:
        log.warning("auth: invalid token")
        abort(403)

def delete_triplet_by_ready_name(ready_name: str):
    """Delete ready BMP, its thumbnail, and matching source(s) by stem."""
    stem = Path(ready_name).stem
    # ready bmp
    try:
        (READY_DIR / ready_name).unlink(missing_ok=True)
    except Exception:
        pass
    # thumb jpg
    try:
        (THUMB_DIR / f"{stem}.jpg").unlink(missing_ok=True)
    except Exception:
        pass
    # any source with same stem + any extension
    for p in SRC_DIR.glob(stem + ".*"):
        try:
            p.unlink()
        except Exception:
            pass
    # clear symlink if it pointed here
    try:
        if LINK_PATH.is_symlink() and LINK_PATH.resolve().name == ready_name:
            LINK_PATH.unlink(missing_ok=True)
    except Exception:
        pass

# ========================
# Routes
# ========================
@app.route("/")
def home():
    current = None
    if LINK_PATH.is_symlink():
        try:
            current = LINK_PATH.resolve().name
        except Exception:
            try:
                current = str(LINK_PATH.readlink())
            except Exception:
                current = None
    return render_template(
        "index.html",
        items=list_ready(),
        current=current,
        token=TOKEN,
        version=__version__,
    )

@app.route("/upload", methods=["POST"])
def upload():
    require_token(request)

    # Accept both "files" and "files[]"
    files = request.files.getlist("files")
    if not files:
        files = request.files.getlist("files[]")

    log.info("upload: received %d file fields", len(files))
    if not files:
        log.warning("upload: no files in request (check form name & enctype)")
        return redirect(url_for("home"))

    saved = 0
    for f in files:
        try:
            if not f or not f.filename:
                continue
            # safe filename (browser can send odd characters)
            safe = secure_filename(f.filename)
            if not safe:
                safe = f"upload_{secrets.token_hex(4)}.jpg"

            # Save raw first
            raw_tmp = SRC_DIR / safe
            f.save(raw_tmp)
            log.info("upload: saved raw %s", raw_tmp.name)

            # Normalize HEIC -> JPEG if needed
            raw = normalize_to_jpeg_if_heic(raw_tmp)

            # Create timestamped base name for READY/THUMB
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            base = f"{stamp}-{Path(raw).stem}"

            # Rename/move source to match the same STEM, so delete can find it
            src_final = SRC_DIR / f"{base}{Path(raw).suffix.lower()}"
            try:
                if raw != src_final:
                    raw.replace(src_final)
                    raw = src_final
            except Exception as e:
                log.warning("upload: could not rename source to %s: %s", src_final.name, e)

            ready_path = READY_DIR / f"{base}.bmp"
            thumb_path = THUMB_DIR  / f"{base}.jpg"

            # Convert for e-paper + make thumbnail
            frame = prepare_epaper_frame(raw)
            frame.save(ready_path, "BMP")

            thumb_w = 320
            thumb_h = int(thumb_w * H / W)
            frame.convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS).save(thumb_path, "JPEG", quality=85)

            saved += 1
            log.info("upload: prepared %s (+thumb)", ready_path.name)

        except Exception as e:
            log.exception("upload: error handling one file: %s", e)
            continue

    log.info("upload: prepared %d image(s) total", saved)
    return redirect(url_for("home"))

@app.route("/set_current", methods=["POST"])
def set_current():
    require_token(request)
    name = request.form.get("name", "")
    if not name:
        abort(400)
    try:
        set_symlink(name)
        log.info("current: now %s", name)
    except Exception as e:
        log.exception("current: failed: %s", e)
    return redirect(url_for("home"))

@app.route("/delete_selected", methods=["POST"])
def delete_selected():
    require_token(request)
    names = request.form.getlist("names")
    if not names:
        return redirect(url_for("home"))
    for n in set(names):
        delete_triplet_by_ready_name(n)
        log.info("delete: %s (ready/src/thumb)", n)
    return redirect(url_for("home"))

@app.route("/ready/<path:name>")
def get_ready(name):
    return send_from_directory(READY_DIR, name)

@app.route("/thumbs/<path:name>")
def get_thumb(name):
    return send_from_directory(THUMB_DIR, name)

if __name__ == "__main__":
    # For dev; in service we rely on RotatingFileHandler and systemd
    app.run(host="0.0.0.0", port=5000, debug=False)