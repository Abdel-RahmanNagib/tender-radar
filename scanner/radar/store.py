"""State kept as JSON files inside app/data – the app reads them, and in the cloud they are saved in the
repository after every run (so nothing is lost and nothing is sent twice)."""
import json
import os
from datetime import timedelta

from .common import parse_date


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0, separators=(",", ":"))
    os.replace(tmp, path)


class Store:
    def __init__(self, data_dir):
        self.dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.tenders_path = os.path.join(data_dir, "tenders.json")
        self.state_path = os.path.join(data_dir, "state.json")
        self.status_path = os.path.join(data_dir, "status.json")
        doc = _load(self.tenders_path, {})
        self.records = {r["uid"]: r for r in doc.get("tenders", [])}
        self.state = _load(self.state_path, {})
        self.state.setdefault("seen", {})
        self.state.setdefault("telegram_chats", [])
        self.state.setdefault("telegram_offset", 0)
        # a lost state file must not cause a flood: everything already in the app counts as seen
        for uid, r in self.records.items():
            self.state["seen"].setdefault(uid, r.get("first_seen", "")[:10])

    @property
    def initialized(self):
        return bool(self.state.get("initialized"))

    def is_new(self, uid):
        return uid not in self.state["seen"]

    def add(self, rec):
        self.records[rec["uid"]] = rec
        self.state["seen"][rec["uid"]] = rec["first_seen"][:10]

    def mark_seen(self, uid, day):
        self.state["seen"].setdefault(uid, day)

    def prune(self, today):
        keep = {}
        for uid, r in self.records.items():
            d = parse_date(r.get("deadline"))
            seen = parse_date(r.get("first_seen", "")[:10]) or today
            if d and d < today - timedelta(days=14):
                continue
            if not d and seen < today - timedelta(days=45):
                continue
            keep[uid] = r
        self.records = keep
        cutoff = (today - timedelta(days=365)).isoformat()
        self.state["seen"] = {u: s for u, s in self.state["seen"].items() if (s or "9999") >= cutoff}

    def open_records(self, today):
        out = []
        for r in self.records.values():
            d = parse_date(r.get("deadline"))
            if not d or d >= today:
                out.append(r)
        return out

    def save(self, status, generated, office, reached_sources=True):
        rows = sorted(self.records.values(), key=lambda r: r.get("first_seen", ""), reverse=True)
        _save(self.tenders_path, {"generated": generated, "office": office, "count": len(rows), "tenders": rows})
        if reached_sources:  # a scan where every source failed is not a real first run
            self.state["initialized"] = True
        _save(self.state_path, self.state)
        _save(self.status_path, status)
