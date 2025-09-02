# artbox — uploader

Mobile-ready FastAPI uploader that saves files to a staging directory and captures quick seed metadata. Designed to keep your data root (/srv/art) clean and backup-friendly while the app code lives under /opt/artbox.

## Install (server)

```bash
# 1) clone
sudo mkdir -p /opt/artbox
cd /opt
sudo git clone https://github.com/<you>/artbox.git
cd artbox

# 2) prepare system python env & service
make install
```

Note:
- The install target creates a virtualenv at `/opt/artbox/venv` and installs a systemd service. These steps require sudo and will run privileged commands (including the venv creation itself).
- If you previously created `/opt/artbox/venv` with sudo and saw a "Permission denied" during `python3 -m venv`, just rerun `make install` after this fix — the venv creation now runs with sudo as well.

Open `http://SERVER_IP:PORT` on your phone (same Wi-Fi).
Use the Upload page for files + quick notes; view Gallery for recent files.

## Update flow

From GitHub:

```bash
cd /opt/artbox
sudo git pull --rebase
make update
```

Local dev (without touching the service):

```bash
# optional: local venv for development
python3 -m venv .venv
. .venv/bin/activate
pip install -r uploader/requirements.txt

# in your cloned repo (e.g. ~/code/artbox)
make dev
# serves from your working copy; writes to /tmp/uploads
```

## Data layout (staging first)

- Code & venv: `/opt/artbox`
- Config: `/etc/artbox/uploader.env`
- Staging uploads (safe to automate): `/srv/art/incoming`
- Your guarded data root: `/srv/art` (back this up; downstream tools can move from incoming → work/)

## Samba (read-only view of /srv/art)

`/etc/samba/smb.conf`:

```
[Art]
   path = /srv/art
   browseable = yes
   read only = yes
   guest ok = no
   valid users = YOURUSER
```

Apply:

```bash
sudo systemctl restart smbd
```

## Seed metadata sidecars

Each upload batch writes a small JSON next to the files in `/srv/art/incoming`:

```json
{
  "saved": ["IMG_0001_2025-09-01_aaaa.jpg", "..."],
  "seed": { "title": "Horizon Strike", "notes": "matte finish", "tags": ["10x10","orange","blue"] },
  "timestamp": "2025-09-01T23:31:44Z"
}
```

Downstream tools (worker/admin) can merge this into per-piece `meta.yml`.

## Security

- Keep this app on LAN or set `UPLOAD_TOKEN` in `/etc/artbox/uploader.env`.
- If you later expose it, front it with Caddy/Nginx + auth.

## Next steps (optional)

- Add a worker to auto-generate web/thumb variants and move files into `/srv/art/work/<piece>/…`.
- Add an admin UI to browse pieces, edit metadata, draft captions, and publish.

