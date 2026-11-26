"""Relay between the office-PC helper and the cloud scan, through an ntfy topic.

Some portals (Qatar Monaqasat, Kuwait CAPT) refuse cloud servers but open normally from the office
network. The PC helper scans them, signs a compressed snapshot of what it found, and posts it to a
relay topic. The cloud scan downloads the snapshots, accepts only those whose Ed25519 signature
matches the public key in the repository, and treats the tenders like any other source.
"""
import base64
import json
import ssl
import urllib.request
import zlib
from datetime import date, datetime

from . import ed25519
from .common import USER_AGENT, http, parse_date

MAGIC = "TRR1"
_CTX = ssl.create_default_context()
DATE_KEYS = ("published", "deadline", "inquiry_deadline", "opening_date")


def jsonable(t):
    out = {}
    for k, v in t.items():
        if k.startswith("_"):
            continue
        out[k] = v.isoformat() if isinstance(v, (date, datetime)) else v
    return out


def restore_item(it):
    t = dict(it)
    for k in DATE_KEYS:
        t[k] = parse_date(t.get(k))
    t.setdefault("extra", {})
    t.setdefault("contact", {})
    t["_detail_done"] = True  # the PC already opened the notice page; the cloud cannot reach it
    t["via_pc"] = True
    return t


def pack(snapshot):
    return zlib.compress(json.dumps(snapshot, ensure_ascii=False, default=str, separators=(",", ":"))
                         .encode("utf-8"), 9)


def _send(url, body, method, headers=None):
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=40, context=_CTX) as r:
        return r.read()


def publish(server, topic, secret, snapshot, log=print, chunk=3600):
    """PC side. Sends the signed snapshot as an ntfy attachment, or in signed text parts if attachments fail."""
    data = pack(snapshot)
    sig = base64.b64encode(ed25519.sign(secret, data)).decode()
    sid = snapshot["id"]
    url = f"{server.rstrip('/')}/{topic}"
    try:
        _send(url, data, "PUT", {"Filename": f"snapshot-{sid}.bin", "Message": f"{MAGIC} snap={sid} sig={sig}"})
        return f"attachment {len(data)} bytes"
    except Exception as e:  # noqa: BLE001
        log(f"  attachment upload failed ({e}); sending text parts")
    b64 = base64.b64encode(data).decode()
    parts = [b64[i:i + chunk] for i in range(0, len(b64), chunk)] or [""]
    for i, part in enumerate(parts, 1):
        _send(url, f"{MAGIC} snap={sid} part={i}/{len(parts)} sig={sig} data={part}".encode("ascii"), "POST")
    return f"{len(parts)} text parts"


def http_bytes(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return r.read()


def fetch_snapshots(server, topic, public_key, since="12h", get_text=None, get_bytes=None):
    """Cloud side. Returns (valid snapshots oldest first, error strings)."""
    get_text, get_bytes = get_text or http, get_bytes or http_bytes
    raw = get_text(f"{server.rstrip('/')}/{topic}/json?poll=1&since={since}", timeout=25, retries=1)
    groups, order = {}, []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except ValueError:
            continue
        txt = (m.get("message") or "").strip()
        if m.get("event") != "message" or not txt.startswith(MAGIC + " "):
            continue
        kv = dict(p.split("=", 1) for p in txt.split()[1:] if "=" in p)
        sid, sig = kv.get("snap"), kv.get("sig")
        if not sid or not sig:
            continue
        if sid not in groups:
            groups[sid] = {"sig": sig, "parts": {}, "n": 0, "att": None}
            order.append(sid)
        g = groups[sid]
        att = m.get("attachment") or {}
        if att.get("url"):
            g["att"] = att["url"]
        if "part" in kv and "data" in kv:
            i, n = kv["part"].split("/")
            g["parts"][int(i)] = kv["data"]
            g["n"] = int(n)
    snaps, errors = [], []
    for sid in order:
        g = groups[sid]
        try:
            if g["att"]:
                data = get_bytes(g["att"])
            elif g["n"] and len(g["parts"]) == g["n"]:
                data = base64.b64decode("".join(g["parts"][i] for i in range(1, g["n"] + 1)))
            else:
                continue
            if not ed25519.verify(public_key, data, base64.b64decode(g["sig"])):
                errors.append(f"office PC relay: snapshot {sid} rejected (signature does not match)")
                continue
            snaps.append(json.loads(zlib.decompress(data).decode("utf-8")))
        except Exception as e:  # noqa: BLE001  (expired attachment, network)
            errors.append(f"office PC relay: snapshot {sid}: {e}"[:220])
    snaps.sort(key=lambda s: s.get("ts", ""))
    return snaps, errors
