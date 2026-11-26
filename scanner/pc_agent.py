#!/usr/bin/env python3
"""مساعد كمبيوتر المكتب — Tender Radar office-PC helper.

Qatar's Monaqasat and Kuwait's CAPT refuse cloud servers but open normally from the office
network. This script scans them, keeps what suits the office, signs the result with the PC's own
key and posts it to the relay topic. The hourly cloud scan on GitHub picks it up, adds it to the
app and sends the notifications. Nothing here needs a password or a GitHub token.

    python pc_agent.py [HOME_FOLDER]
"""
import os
import sys

if os.name == "nt":  # QGIS/ArcGIS Python: SSL libraries live in the program's bin folder
    for _d in os.environ.get("TR_DLL_DIRS", "").split(";"):
        if _d and os.path.isdir(_d):
            try:
                os.add_dll_directory(_d)
            except OSError:
                pass

import json  # noqa: E402
import platform  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import uuid  # noqa: E402
from datetime import date  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from radar import ed25519, relay  # noqa: E402
from radar.common import http, norm, utc_now_iso  # noqa: E402
from radar.engine import load_json  # noqa: E402
from radar.scoring import Matcher  # noqa: E402
from radar.sources import COLLECTORS, fetch_detail  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]


def log(msg):
    print(msg, flush=True)


def browser_page(url, timeout=90):
    """Fallback for portals behind a browser check: let the installed Chrome/Edge render the page."""
    exe = next((b for b in BROWSERS if os.path.exists(b)), None)
    if not exe:
        raise RuntimeError("no Chrome/Edge found for the browser fallback")
    profile = tempfile.mkdtemp(prefix="tr-browser-")
    try:
        r = subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                            f"--user-data-dir={profile}", "--virtual-time-budget=10000", "--dump-dom", url],
                           capture_output=True, timeout=timeout)
        html = r.stdout.decode("utf-8", errors="replace")
        if len(html) < 500:
            raise RuntimeError(f"browser returned {len(html)} bytes")
        return html
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def pc_fetch(url, data=None, headers=None, method=None, retries=1, timeout=None):
    try:
        return http(url, data=data, headers=headers, method=method, retries=retries, timeout=timeout)
    except urllib.error.HTTPError as e:
        if data is None and e.code in (403, 429, 503):
            log(f"    {e.code} from {url[:70]} — retrying through the browser")
            return browser_page(url)
        raise


def load_key(home):
    path = os.path.join(home, "data", "pc_key.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            secret = bytes.fromhex(json.load(f)["private"])
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        secret = ed25519.new_private_key()
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"private": secret.hex(), "created": utc_now_iso(),
                       "note": "Private key of this PC. Keep it here; never share or upload it."}, f)
    public = ed25519.public_key(secret).hex()
    with open(os.path.join(home, "PUBLIC-KEY.txt"), "w", encoding="utf-8") as f:
        f.write(public + "\n")
    return secret, public


def worth_opening(m, t):
    """Open a Qatar notice page only if the title hints at consulting work or one of the disciplines."""
    title = norm(t.get("title", "") + " " + t.get("description", ""))
    return bool(m._hits(title, m.consult) or any(m._hits(title, p) for _, _, _, p in m.disciplines))


def main(home=None):
    home = os.path.abspath(home or os.environ.get("TENDER_RADAR_HOME") or os.path.dirname(HERE))
    settings = load_json(os.path.join(HERE, "settings.json"))
    profile = load_json(os.path.join(HERE, "profile.json"))
    rcfg = profile["sources"].get("pc_relay", {})
    secret, public = load_key(home)
    countries = settings.get("countries") or list(profile["countries"])
    matcher = Matcher(profile, settings.get("min_level", "low"))
    today = date.today()
    log(f"[{utc_now_iso()}] office-PC scan — key {public[:12]}…")

    items, status = [], []
    for name in rcfg.get("pc_sources", ["monaqasat", "kuwait_capt"]):
        fn = COLLECTORS.get(name)
        if not fn:
            continue
        t0 = time.time()
        try:
            got = fn(profile["sources"].get(name, {}), countries, fetch=pc_fetch)
        except Exception as e:  # noqa: BLE001
            status.append({"key": name, "count": 0, "ok": False, "error": str(e)[:200]})
            log(f"  {name}: failed ({e})")
            continue
        errs = [i["_error"] for i in got if "_error" in i]
        got = [i for i in got if "_error" not in i]
        opened, kept = 0, 0
        for t in got:
            if name == "monaqasat" and opened < 40 and worth_opening(matcher, t):
                fetch_detail(t, pc_fetch)
                opened += 1
            ok, _info = matcher.evaluate(t, today)
            if ok:
                t["detail_text"] = (t.get("detail_text") or "")[:4000]
                items.append(t)
                kept += 1
        status.append({"key": name, "count": len(got), "ok": bool(got) or not errs, "failed_pages": len(errs),
                       "matched": kept, "error": errs[0][:200] if errs and not got else ""})
        log(f"  {name}: {len(got)} read, {opened} opened, {kept} suitable"
            + (f", {len(errs)} pages failed: {errs[0][:120]}" if errs else "") + f" ({time.time() - t0:.0f}s)")

    snapshot = {"v": 1, "id": uuid.uuid4().hex[:12], "ts": utc_now_iso(), "host": platform.node(),
                "public_key": public, "items": [relay.jsonable(t) for t in items], "sources": status}
    if not rcfg.get("topic"):
        log("no relay topic in profile.json — nothing sent")
        return 1
    how = relay.publish(rcfg.get("server", "https://ntfy.sh"), rcfg["topic"], secret, snapshot, log)
    log(f"✔ sent {len(items)} suitable tenders to the cloud scan ({how})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
