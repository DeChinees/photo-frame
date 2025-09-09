#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
from datetime import datetime
from flask import (
    Flask, request, redirect, url_for,
    render_template, send_from_directory, abort
)
from PIL import Image

# --- Paths ---
BASE = Path(__file__).resolve().parent
PHOTOS_BASE = BASE / "photos"
SRC_DIR   = PHOTOS_BASE / "photos_source"
READY_DIR = PHOTOS_BASE / "photos_ready"
THUMB_DIR = PHOTOS_BASE / "thumbs"
LINK_PATH = PHOTOS_BASE / "current.bmp"

W, H = 800, 480
PALETTE = [
    (255, 255, 255),
    (0, 0, 0),
    (255, 0, 0),
    (255, 255, 0),
    (0, 0, 255),
    (0, 255, 0),
]
TOKEN = os.environ.get("FRAME_TOKEN", "changeme123")

for p in (SRC_DIR, READY_DIR, THUMB_DIR):
    p.mkdir(parents=True, exist_ok=True)

# --- HEIC helper ---
HEIC_EXTS = {".heic", ".heif"}

def normalize_to_jpeg_if_heic(path: Path) -> Path:
    """If file is HEIC/HEIF, convert to JPEG with heif-convert, return new path."""
    if path.suffix.lower() not in HEIC_EXTS:
        return path
    jpg = path.with_suffix(".jpg")
    try:
        subprocess.run(
            ["heif-convert", str(path), str(jpg)],
            check=True, capture_output=True
        )
        path.unlink(missing_ok=True)
        return jpg
    except Exception as e:
        print("[upload] HEIC convert failed:", e)
        return path

# --- Image conversion ---
def to_frame(src: Path, dst: Path, thumb: Path):
    im = Image.open(src).convert("RGB")
    im = im.resize((W, H))
    im = im.quantize(palette=Image.new("P", (1, 1), 0), colors=len(PALETTE))
    im.save(dst, "BMP")

    t = im.copy()
    t.thumbnail((200, 120))
    t.save(thumb, "JPEG", quality=80)

def list_ready():
    return sorted([p.name for p in READY_DIR.glob("*.bmp")])

def set_symlink(name: str):
    LINK_PATH.unlink(missing_ok=True)
    (READY_DIR / name).symlink_to(LINK_PATH)

def require_token(req):
    t = req.form.get("token") or req.args.get("token")
    if t != TOKEN:
        abort(403)

# --- Flask app ---
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["TEMPLATES_AUTO_RELOAD"] = True

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
        version="0.1.0",
    )

@app.route("/upload", methods=["POST"])
def upload():
    require_token(request)
    files = request.files.getlist("files")
    for f in files:
        if not f.filename:
            continue
        raw = SRC_DIR / f.filename
        f.save(raw)

        raw = normalize_to_jpeg_if_heic(raw)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{stamp}-{Path(raw).stem}"
        out = READY_DIR / f"{base}.bmp"
        thumb = THUMB_DIR / f"{base}.jpg"
        try:
            to_frame(raw, out, thumb)
        except Exception as e:
            print("[upload] conversion failed:", e)
            continue
    return redirect(url_for("home"))

@app.route("/set_current", methods=["POST"])
def set_current():
    require_token(request)
    name = request.form.get("name")
    if not name:
        abort(400)
    set_symlink(name)
    return redirect(url_for("home"))

@app.route("/delete_selected", methods=["POST"])
def delete_selected():
    require_token(request)
    names = request.form.getlist("names")
    for n in names:
        bmp = READY_DIR / n
        jpg = THUMB_DIR / (Path(n).stem + ".jpg")
        src = SRC_DIR / (Path(n).stem + Path(n).suffix)
        for p in (bmp, jpg, src):
            if p.exists():
                p.unlink()
        if LINK_PATH.is_symlink() and LINK_PATH.resolve().name == n:
            LINK_PATH.unlink(missing_ok=True)
    return redirect(url_for("home"))

@app.route("/ready/<name>")
def get_ready(name):
    return send_from_directory(READY_DIR, name)

@app.route("/thumbs/<name>")
def get_thumb(name):
    return send_from_directory(THUMB_DIR, name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)