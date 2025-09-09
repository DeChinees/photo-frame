#!/usr/bin/env python3
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, request, redirect, url_for, render_template_string, send_from_directory, abort, render_template
from PIL import Image
import pillow_heif

# --- Paths & constants ---
BASE      = Path(__file__).resolve().parent
SRC_DIR   = BASE / "photos_src"
READY_DIR = BASE / "photos_ready"
THUMB_DIR = BASE / "thumbs"
LINK_PATH = BASE / "current.bmp"   # symlink to the chosen ready image
__version__ = "0.0.1"

W, H = 800, 480
PALETTE = [(255,255,255),(0,0,0),(255,0,0),(255,255,0),(0,0,255),(0,255,0)]
TOKEN = os.environ.get("FRAME_TOKEN", "changeme123")

for p in (SRC_DIR, READY_DIR, THUMB_DIR):
    p.mkdir(parents=True, exist_ok=True)

# Let Pillow open HEIC from iPhones
pillow_heif.register_heif_opener()

app = Flask(__name__, template_folder="templates", static_folder="static")
# helpful during development:
app.config["TEMPLATES_AUTO_RELOAD"] = True

# --- Helpers ---
def _pal():
    pal = Image.new("P",(1,1))
    flat=[]
    for r,g,b in PALETTE: flat += [r,g,b]
    flat += [0,0,0]*(256-len(PALETTE))
    pal.putpalette(flat)
    return pal

PAL_IMG = _pal()

def to_frame(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    iw, ih = img.size
    scale = min(W/iw, H/ih)
    nw, nh = max(1,int(iw*scale)), max(1,int(ih*scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB",(W,H),(255,255,255))
    canvas.paste(img, ((W-nw)//2,(H-nh)//2))
    return canvas.quantize(palette=PAL_IMG, dither=Image.FLOYDSTEINBERG)  # 'P'

def list_ready():
    return sorted([p.name for p in READY_DIR.glob("*.bmp")])

def set_symlink(target: Path):
    tmp_link = LINK_PATH.with_suffix(".tmp")
    if tmp_link.exists() or tmp_link.is_symlink():
        tmp_link.unlink()
    # relative link (safe for moving the folder)
    tmp_link.symlink_to(target)
    tmp_link.replace(LINK_PATH)

def require_token(req):
    if req.headers.get("X-Auth-Token") != TOKEN and req.form.get("token") != TOKEN:
        abort(401)

def delete_by_ready_name(ready_name: str):
    """Delete original(s) with matching stem, the ready BMP, and the thumbnail.
       If current.bmp points to this file, unlink it."""
    ready_path = READY_DIR / ready_name
    stem = Path(ready_name).stem

    if ready_path.exists():
        try: ready_path.unlink()
        except Exception: pass

    thumb_path = THUMB_DIR / (stem + ".jpg")
    if thumb_path.exists():
        try: thumb_path.unlink()
        except Exception: pass

    for p in SRC_DIR.glob(stem + ".*"):
        try: p.unlink()
        except Exception: pass

    try:
        if LINK_PATH.is_symlink() and LINK_PATH.resolve().name == ready_name:
            LINK_PATH.unlink(missing_ok=True)
    except Exception:
        pass

# --- Routes ---
@app.route("/")
def home():
    current = None
    if LINK_PATH.is_symlink():
        try: current = LINK_PATH.resolve().name
        except Exception:
            try: current = str(LINK_PATH.readlink())
            except Exception: current = None
    return render_template("index.html",
                           items=list_ready(),
                           current=current,
                           token=TOKEN,
                           version=__version__)

@app.route("/upload", methods=["POST"])
def upload():
    require_token(request)
    files = request.files.getlist("files")
    if not files:
        abort(400, "No files")

    for f in files:
        if not f.filename:
            continue
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe = "".join(c for c in f.filename if c.isalnum() or c in "._-")
        raw = SRC_DIR / f"{ts}-{safe}"
        f.save(raw)

        im = Image.open(raw).convert("RGB")
        frame = to_frame(im)
        out = READY_DIR / (raw.stem + ".bmp")
        frame.save(out, "BMP")

        # Thumbnail from prepared frame (always 800x480 origin)
        th = THUMB_DIR / (out.stem + ".jpg")
        thumb_w = 320
        thumb_h = int(thumb_w * H / W)
        frame.convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS).save(th, "JPEG", quality=85)

    # NOTE: we intentionally do NOT set current.bmp here anymore.
    return redirect(url_for("home"))

@app.route("/set_current", methods=["POST"])
def set_current():
    require_token(request)
    name = request.form.get("name","")
    target = READY_DIR / name
    if not target.exists():
        abort(404)
    set_symlink(target)
    return redirect(url_for("home"))

@app.route("/delete_selected", methods=["POST"])
def delete_selected():
    require_token(request)
    names = request.form.getlist("names")  # list of ready filenames (*.bmp)
    if not names:
        return redirect(url_for("home"))

    seen = set()
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        if (READY_DIR / name).exists():
            delete_by_ready_name(name)

    return redirect(url_for("home"))

@app.route("/ready/<path:name>")
def get_ready(name):
    return send_from_directory(READY_DIR, name)

@app.route("/thumbs/<path:name>")
def get_thumb(name):
    return send_from_directory(THUMB_DIR, name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)