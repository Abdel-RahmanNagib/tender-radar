"""Tender Radar – office-PC helper launcher (Windows Task Scheduler runs it every hour).

Each run: refresh the scanner code from the office's GitHub repository, then scan the portals that
refuse cloud servers (Qatar Monaqasat, Kuwait CAPT) and send the signed results to the cloud scan.
Log: data\\pc-helper.log      Private key of this PC: data\\pc_key.json (never share it).
"""
import os
import sys

HOME = os.path.dirname(os.path.abspath(__file__))

# QGIS / ArcGIS ship their own Python; its SSL libraries sit in the program's bin folder.
if os.name == "nt":
    for d in os.environ.get("TR_DLL_DIRS", "").split(";"):
        if d and os.path.isdir(d):
            try:
                os.add_dll_directory(d)
            except OSError:
                pass

import io  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import urllib.request  # noqa: E402
import zipfile  # noqa: E402
from datetime import datetime  # noqa: E402

REPO_ZIP = "https://codeload.github.com/Abdel-RahmanNagib/tender-radar/zip/refs/heads/main"
CODE = os.path.join(HOME, "code")
DATA = os.path.join(HOME, "data")
LOG = os.path.join(DATA, "pc-helper.log")


def update_code():
    try:
        req = urllib.request.Request(REPO_ZIP, headers={"User-Agent": "TenderRadar-PC-helper"})
        blob = urllib.request.urlopen(req, timeout=90).read()
        z = zipfile.ZipFile(io.BytesIO(blob))
        new = CODE + ".new"
        shutil.rmtree(new, ignore_errors=True)
        for name in z.namelist():
            _, _, rel = name.partition("/")
            if not rel.startswith("scanner/") or name.endswith("/") or "/tests/" in rel:
                continue
            dest = os.path.join(new, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(z.read(name))
        if not os.path.exists(os.path.join(new, "scanner", "pc_agent.py")):
            return "code update skipped (download incomplete)"
        old = CODE + ".old"
        shutil.rmtree(old, ignore_errors=True)
        if os.path.exists(CODE):
            os.replace(CODE, old)
        os.replace(new, CODE)
        shutil.rmtree(old, ignore_errors=True)
        return "code updated from GitHub"
    except Exception as e:  # noqa: BLE001
        return f"code update skipped ({e}); using the copy on this PC"


def trim_log(limit=300_000):
    try:
        if os.path.getsize(LOG) > limit:
            with open(LOG, encoding="utf-8", errors="replace") as f:
                tail = f.read()[-limit // 2:]
            with open(LOG, "w", encoding="utf-8") as f:
                f.write(tail)
    except OSError:
        pass


def main():
    os.makedirs(DATA, exist_ok=True)
    started = datetime.now().strftime("%Y-%m-%d %H:%M")
    note = update_code()
    agent = os.path.join(CODE, "scanner", "pc_agent.py")
    if not os.path.exists(agent):
        out, code = f"no scanner code yet ({note})", 1
    else:
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        try:
            r = subprocess.run([sys.executable, agent, HOME], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=1500, env=env)
            out, code = (r.stdout + r.stderr).strip(), r.returncode
        except subprocess.TimeoutExpired:
            out, code = "scan stopped after 25 minutes", 1
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n=== {started} — {note}\n{out}\n(exit {code})\n")
    trim_log()
    print(f"{note}\n{out}")
    return code


if __name__ == "__main__":
    sys.exit(main())
