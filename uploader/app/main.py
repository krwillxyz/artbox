from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from datetime import datetime
import os, re, secrets, shutil, json

# ---------- config ----------
# app root is the folder containing this file (…/uploader/app)
APP_ROOT = Path(__file__).resolve().parent
# ENV comes from /etc/artbox/uploader.env via systemd, but we also support local .env
ENV_FILE = APP_ROOT / ".env"


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    # overlay OS env (systemd EnvironmentFile)
    env.update(os.environ)
    return env


CFG = load_env()
UPLOAD_DIR = Path(CFG.get("UPLOAD_DIR", "/srv/art/incoming"))
DATA_ROOT = Path(CFG.get("DATA_ROOT", "/srv/art"))
UPLOAD_TOKEN = CFG.get("UPLOAD_TOKEN", "")
FILENAME_MODE = CFG.get("FILENAME_MODE", "stamp").lower()
MULTI_UPLOAD = CFG.get("MULTI_UPLOAD", "true").lower() == "true"
GALLERY_LIMIT = int(CFG.get("GALLERY_LIMIT", "60"))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ---------- app ----------
app = FastAPI(title="Art Uploader", docs_url=None, redoc_url=None)

# static (local project static assets; currently empty)
STATIC_DIR = APP_ROOT / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# serve incoming uploads read-only for gallery preview
app.mount("/incoming", StaticFiles(directory=UPLOAD_DIR), name="incoming")

env = Environment(
    loader=FileSystemLoader(APP_ROOT / "templates"),
    autoescape=select_autoescape(["html"]),
)


def tpl(name, **ctx):
    return HTMLResponse(env.get_template(name).render(**ctx))


def sanitize(name: str) -> str:
    name = name.replace("\\", "/").split("/")[-1]
    base, dot, ext = name.rpartition(".")
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-") or "file"
    ext = re.sub(r"[^A-Za-z0-9]+", "", ext)[:10]
    return f"{base}.{ext}" if ext else base


def stamped(name: str) -> str:
    base, dot, ext = name.rpartition(".")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rand = secrets.token_hex(2)
    return f"{base}_{stamp}_{rand}.{ext}" if ext else f"{base}_{stamp}_{rand}"


def save_sidecar(
    dst_dir: Path,
    saved_names: list[str],
    seed_title: str | None,
    seed_notes: str | None,
    seed_tags: str | None,
):
    """
    Write a tiny JSON next to uploads capturing your in-the-moment thoughts.
    This is staging metadata; downstream tools can merge into meta.yml later.
    """
    sidecar = {
        "saved": saved_names,
        "seed": {
            "title": seed_title or None,
            "notes": seed_notes or None,
            "tags": [t.strip() for t in (seed_tags or "").split(",") if t.strip()],
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    # single sidecar per batch
    batch_name = f"batch_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    (dst_dir / batch_name).write_text(json.dumps(sidecar, indent=2))


# ---------- routes ----------
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return tpl(
        "index.html",
        requires_token=bool(UPLOAD_TOKEN),
        multi=MULTI_UPLOAD,
        upload_dir=str(UPLOAD_DIR),
        data_root=str(DATA_ROOT),
    )


@app.get("/gallery", response_class=HTMLResponse)
def gallery(request: Request):
    # list recent files in UPLOAD_DIR
    files = []
    for p in sorted(UPLOAD_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and not p.name.endswith(".json"):
            files.append(
                {
                    "name": p.name,
                    "size": p.stat().st_size,
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime),
                }
            )
        if len(files) >= GALLERY_LIMIT:
            break
    return tpl("gallery.html", files=files)


@app.post("/upload")
async def upload(
    token: str = Form(default=""),
    seed_title: str = Form(default=""),
    seed_notes: str = Form(default=""),
    seed_tags: str = Form(default=""),
    file: UploadFile = File(None),
    files: list[UploadFile] = File(None),
):
    if UPLOAD_TOKEN and token != UPLOAD_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

    incoming: list[UploadFile] = []
    if MULTI_UPLOAD and files:
        incoming = files
    elif file:
        incoming = [file]
    else:
        raise HTTPException(status_code=400, detail="No file(s) provided")

    saved = []
    for f in incoming:
        safe = sanitize(f.filename)
        fname = stamped(safe) if FILENAME_MODE == "stamp" else safe
        dst = UPLOAD_DIR / fname
        with dst.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(fname)

    # initial seed sidecar for this batch
    try:
        save_sidecar(UPLOAD_DIR, saved, seed_title, seed_notes, seed_tags)
    except Exception:
        # don't block uploads if sidecar fails; just continue
        pass

    names = ",".join(saved)
    return RedirectResponse(url=f"/?ok=1&name={names}", status_code=303)

