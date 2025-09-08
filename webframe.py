#!/usr/bin/env python3
import os, time
from pathlib import Path
from datetime import datetime
from flask import Flask, request, redirect, url_for, render_template_string, send_from_directory, abort
from PIL import Image
import pillow_heif

# --- Paths & constants ---
BASE      = Path(__file__).resolve().parent
SRC_DIR   = BASE / "photos_src"
READY_DIR = BASE / "photos_ready"
THUMB_DIR = BASE / "thumbs"
LINK_PATH = BASE / "current.bmp"   # symlink: points to selected ready image

W, H = 800, 480
PALETTE = [(255,255,255),(0,0,0),(255,0,0),(255,255,0),(0,0,255),(0,255,0)]
TOKEN = os.environ.get("FRAME_TOKEN", "changeme123")

for p in (SRC_DIR, READY_DIR, THUMB_DIR):
    p.mkdir(parents=True, exist_ok=True)

pillow_heif.register_heif_opener()
app = Flask(__name__)

# --- Template (Gallery now has checkboxes + bulk delete) ---
HTML = r"""
<!doctype html><meta name=viewport content="width=device-width, initial-scale=1">
<title>Photo Frame</title>
<style>
 body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:900px;margin:24px auto;padding:0 12px}
 .box{border:1px solid #ccc;padding:12px;border-radius:10px;margin:12px 0}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}
 img{width:100%;border-radius:8px;border:1px solid #ddd}
 .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 .muted{color:#666}
 button{cursor:pointer}
 label.chk{display:block;margin-bottom:6px}
</style>

<div class=box>
  <h2>📷 Upload</h2>
  <form method=post action="{{url_for('upload')}}" enctype=multipart/form-data>
    <input type=file name=files multiple accept="image/*,image/heic"><br>
    <label><input type=checkbox name=display checked> Display newest after upload</label>
    <input type=hidden name=token value="{{token}}">
    <div class=row><button>Upload</button></div>
    <div class=muted>Tip: Add this page to Home Screen on iPhone for an app-like feel.</div>
  </form>
</div>

<div class=box>
  <h3>Ready images ({{items|length}})</h3>
  {% if items %}
  <form method="post" action="{{ url_for('delete_selected') }}" onsubmit="return confirm('Delete selected images?');">
    <input type="hidden" name="token" value="{{ token }}">
    <div class="row" style="margin:8px 0">
      <button type="submit">🗑️ Delete selected</button>
    </div>
    <div class=grid>
      {% for it in items %}
        <div>
          <label class="chk">
            <input type="checkbox" name="names" value="{{ it }}"> Select
          </label>
          <a href="{{ url_for('get_ready', name=it) }}" target="_blank">
            <img src="{{ url_for('get_thumb', name=it.rsplit('.',1)[0]+'.jpg') }}" alt="{{ it }}">
          </a>
          <div class="row" style="margin-top:6px">
            <form method="post" action="{{ url_for('set_current') }}" style="display:inline">
              <input type="hidden" name="name" value="{{ it }}">
              <input type="hidden" name="token" value="{{ token }}">
              <button type="submit">Display</button>
            </form>
          </div>
          <div class="muted">{{ it }}</div>
        </div>
      {% endfor %}
    </div>
  </form>
  {% else %}
    <p class="muted">No prepared images yet.</p>
  {% endif %}
</div>

<div class=box>
  <h3>Current target</h3>
  <p class=muted>{{ current or "None" }}</p>
</div>
"""

# --- Helpers ---
def _pal():
    pal = Image.new("P",(1,1))
    flat=[]
    for r,g,b in PALETTE: flat += [r,g,b]
    flat += [0,0,0]*(256-len(PALETTE))
    pal.putpalette(flat); return pal
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
    # Only prepared BMPs are displayed
    return sorted([p.name for p in READY_DIR.glob("*.bmp")])

def set_symlink(target: Path):
    tmp_link = LINK_PATH.with_suffix(".tmp")
    if tmp_link.exists() or tmp_link.is_symlink():
        tmp_link.unlink()
    # Use a relative link (so moving the folder keeps the link valid)
    rel_target = target if target.is_absolute() else target
    tmp_link.symlink_to(rel_target)
    tmp_link.replace(LINK_PATH)

def require_token(req):
    if req.headers.get("X-Auth-Token") != TOKEN and req.form.get("token") != TOKEN:
        abort(401)

def delete_by_ready_name(ready_name: str):
    """Delete source(s) with matching stem, the ready BMP, and the thumbnail.
       If current.bmp points to this file, unlink it."""
    ready_path = READY_DIR / ready_name
    stem = Path(ready_name).stem

    # Delete ready BMP
    if ready_path.exists():
        try: ready_path.unlink()
        except Exception: pass

    # Delete thumbnail
    thumb_path = THUMB_DIR / (stem + ".jpg")
    if thumb_path.exists():
        try: thumb_path.unlink()
        except Exception: pass

    # Delete matching originals (any extension)
    for p in SRC_DIR.glob(stem + ".*"):
        try: p.unlink()
        except Exception: pass

    # If the current symlink points to this, remove it (or repoint to another)
    try:
        if LINK_PATH.is_symlink() and LINK_PATH.resolve().name == ready_name:
            LINK_PATH.unlink(missing_ok=True)
            # Optional: repoint to another remaining image
            # remaining = list_ready()
            # if remaining:
            #     set_symlink(READY_DIR / remaining[0])
    except Exception:
        pass

# --- Routes ---
@app.route("/")
def home():
    current = None
    if LINK_PATH.is_symlink():
        try:
            current = LINK_PATH.resolve().name
        except Exception:
            try: current = str(LINK_PATH.readlink())
            except Exception: current = None
    return render_template_string(HTML, items=list_ready(), current=current, token=TOKEN)

@app.route("/upload", methods=["POST"])
def upload():
    require_token(request)
    files = request.files.getlist("files")
    if not files: abort(400, "No files")
    newest = None
    for f in files:
        if not f.filename: continue
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe = "".join(c for c in f.filename if c.isalnum() or c in "._-")
        raw = SRC_DIR / f"{ts}-{safe}"
        f.save(raw)

        # Normalize & prepare frame
        im = Image.open(raw).convert("RGB")
        frame = to_frame(im)
        out = READY_DIR / (raw.stem + ".bmp")
        frame.save(out, "BMP")

        # Thumbnail from prepared frame (guaranteed 800x480)
        th = THUMB_DIR / (out.stem + ".jpg")
        thumb_w = 320
        thumb_h = int(thumb_w * H / W)
        frame.convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS).save(th, "JPEG", quality=85)
        newest = out

    if newest is not None and request.form.get("display"):
        set_symlink(newest)

    return redirect(url_for("home"))

@app.route("/set_current", methods=["POST"])
def set_current():
    require_token(request)
    name = request.form.get("name","")
    target = READY_DIR / name
    if not target.exists(): abort(404)
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
    # Run on all interfaces for phones on LAN
    app.run(host="0.0.0.0", port=5001)