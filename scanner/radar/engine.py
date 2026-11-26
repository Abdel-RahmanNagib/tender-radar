"""One scan: collect -> keep what a consultancy can apply for -> enrich -> notify -> save for the app."""
import json
import os
import time
import traceback
from datetime import date, timedelta

from .build import build_record, refresh_steps
from .common import cairo_now, fmt_date_ar, http, utc_now_iso
from .notify import Notifier, count_ar, days_left
from .scoring import Matcher
from .sources import COLLECTORS, RELAY_INFO, fetch_detail
from .store import Store

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project root


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def channels_from(settings):
    """Notification settings: environment variables (GitHub Secrets) win over settings.json."""
    pc = settings.get("notifications_for_pc_mode", {})
    em = dict(pc.get("email") or {})
    env = os.environ.get
    ch = {
        "console": True,
        "ntfy_topic": env("NTFY_TOPIC") or pc.get("ntfy_topic", ""),
        "ntfy_server": env("NTFY_SERVER") or pc.get("ntfy_server", "https://ntfy.sh"),
        "telegram_token": env("TELEGRAM_BOT_TOKEN") or pc.get("telegram_bot_token", ""),
        "telegram_chat_ids": [x.strip() for x in (env("TELEGRAM_CHAT_IDS") or "").split(",") if x.strip()]
        or pc.get("telegram_chat_ids", []),
        "email": {
            "smtp_host": env("SMTP_HOST") or em.get("smtp_host", ""),
            "smtp_port": env("SMTP_PORT") or em.get("smtp_port", 465),
            "username": env("SMTP_USERNAME") or em.get("username", ""),
            "password": env("SMTP_PASSWORD") or em.get("password", ""),
            "from": env("SMTP_FROM") or em.get("from", ""),
            "to": [x.strip() for x in (env("EMAIL_TO") or "").split(",") if x.strip()] or em.get("to", []),
        },
    }
    return ch


def run_once(settings, profile, data_dir, fetchers=None, notifier=None, today=None, app_url=None, log=print):
    today = today or date.today()
    now_iso = utc_now_iso()
    fetchers = fetchers or {}
    store = Store(data_dir)
    matcher = Matcher(profile, settings.get("min_level", "medium"))
    app_url = app_url if app_url is not None else os.environ.get("APP_URL", "")
    notifier = notifier or Notifier(channels_from(settings), store.state, app_url, log)
    countries = settings.get("countries") or list(profile["countries"])
    enabled = settings.get("sources", {})

    collected, errors, per_source = [], [], []
    for name, fn in COLLECTORS.items():
        if not enabled.get(name, True):
            continue
        scfg = profile["sources"].get(name, {})
        try:
            kw = {"fetch": fetchers[name]} if name in fetchers else {}
            items = fn(scfg, countries, **kw)
            errs = [i["_error"] for i in items if "_error" in i]
            items = [i for i in items if "_error" not in i]
            errors += errs
            per_source.append({"key": name, "count": len(items), "ok": bool(items) or not errs,
                               "failed_pages": len(errs), "error": errs[0][:200] if errs and not items else ""})
            collected += items
            log(f"  {name}: {len(items)}" + ((" (تعذر الوصول)" if not items else f" (تعذر فتح {len(errs)} من صفحاته)")
                                            if errs else ""))
        except Exception as e:  # noqa: BLE001  a broken source never stops the scan
            errors.append(f"{name}: {e}")
            per_source.append({"key": name, "count": 0, "ok": False, "error": str(e)[:200]})
            log(f"  {name}: تعذر الوصول ({e})")
            if os.environ.get("RADAR_DEBUG"):
                traceback.print_exc()

    matched, new, seen_now = [], [], set()
    for t in collected:
        if t["uid"] in seen_now:
            continue
        ok, info = matcher.evaluate(t, today)
        if not ok:
            continue
        seen_now.add(t["uid"])
        matched.append(t)
        rec = store.records.get(t["uid"])
        if rec is not None:  # already known: just follow deadline changes (extensions)
            if t.get("deadline") and rec.get("deadline") and t["deadline"].isoformat() != rec["deadline"]:
                rec["notes"] = (rec.get("notes") or []) + [
                    f"تم تغيير آخر موعد من {fmt_date_ar(rec['deadline'])} إلى {fmt_date_ar(t['deadline'])}"]
                rec["deadline"] = t["deadline"].isoformat()
                rec["updated"] = now_iso
                refresh_steps(rec, today)
            continue
        if store.is_new(t["uid"]):
            new.append((t, info))

    detail_fetch = fetchers.get("detail", http)
    limit_detail = int(settings.get("max_detail_pages", 30))
    budget = time.monotonic() + int(settings.get("detail_time_budget_seconds", 180))
    records = []
    for i, (t, info) in enumerate(new):
        if not t.get("_detail_done") and i < limit_detail and time.monotonic() < budget:
            fetch_detail(t, detail_fetch)
            if t.get("deadline") and t["deadline"] < today:
                store.mark_seen(t["uid"], today.isoformat())
                continue
        records.append(build_record(t, info, today, now_iso))
    order = {"high": 0, "medium": 1, "low": 2}
    records.sort(key=lambda r: (order.get(r["match"]["level"], 3), r.get("deadline") or "9999"))

    notifier.sync_subscribers()
    first_run = not store.initialized
    cap = int(settings.get("max_notifications_per_run", 15))
    for r in records:
        store.add(r)
    if first_run and records:
        notifier.summary(f"📊 رادار المناقصات يعمل الآن – {count_ar(len(records))} مفتوحة",
                         "هذه أول عملية فحص: تم تسجيل كل الفرص المفتوحة حالياً في التطبيق.\n"
                         "من الآن ستصلك رسالة منفصلة لكل فرصة جديدة.")
    elif records:
        for r in records[:cap]:
            notifier.tender(r, today)
        if len(records) > cap:
            notifier.summary(f"📊 {count_ar(len(records))} جديدة", f"أُرسل أهم {cap} فقط، والباقي في التطبيق.")

    open_recs = store.open_records(today)
    _daily_summary(settings, store, notifier, open_recs, today)
    store.prune(today)
    errors += notifier.errors
    status = {
        "last_run": now_iso, "every_minutes": settings.get("check_every_minutes", 60),
        "collected": len(collected), "matched": len(matched), "new": len(records), "open": len(open_recs),
        "sources": per_source, "errors": errors[:20], "notifications_sent": notifier.sent,
        "pc_helper": dict(RELAY_INFO),
        "channels": {"ntfy": bool(notifier.ch.get("ntfy_topic")), "telegram": bool(notifier.ch.get("telegram_token")),
                     "email": notifier._email_on()},
    }
    store.save(status, now_iso, settings.get("office_name", ""), reached_sources=bool(collected))
    _publish_profile(profile, data_dir)
    log(f"\n✔ تم الفحص: {len(collected)} إعلان، {len(matched)} مناسب، {len(records)} جديد، "
        f"{len(open_recs)} فرصة مفتوحة" + (" (أول تشغيل)" if first_run else ""))
    return {"collected": len(collected), "matched": len(matched), "new": records, "errors": errors,
            "first_run": first_run, "status": status}


def _daily_summary(settings, store, notifier, open_recs, today):
    hour = settings.get("daily_summary_hour_cairo")
    if hour is None or not store.initialized:
        return
    now = cairo_now()
    if now.hour < int(hour) or store.state.get("last_summary") == now.date().isoformat():
        return
    soon = sorted([r for r in open_recs if r.get("deadline") and (days_left(r, today) or 99) <= 7],
                  key=lambda r: r["deadline"])
    since = (today - timedelta(days=1)).isoformat()
    new_24h = [r for r in open_recs if (r.get("first_seen") or "")[:10] >= since]
    body = f"الفرص المفتوحة: {len(open_recs)}\nتنتهي خلال 7 أيام: {len(soon)}"
    if soon:
        body += "\nأقربها: " + "، ".join(f"{r['title'][:60]} ({fmt_date_ar(r['deadline'])})" for r in soon[:3])
    body += f"\nجديد خلال آخر 24 ساعة: {len(new_24h)}"
    notifier.summary("☀️ ملخص رادار المناقصات اليوم", body)
    store.state["last_summary"] = now.date().isoformat()


def _publish_profile(profile, data_dir):
    """The app needs the discipline keywords to match your past projects on the device."""
    slim = {"disciplines": [{"id": d["id"], "ar": d["ar"], "keywords": d["keywords"]} for d in profile["disciplines"]]}
    with open(os.path.join(data_dir, "profile.json"), "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False)


def reset_data(data_dir):
    for n in ("tenders.json", "state.json", "status.json"):
        p = os.path.join(data_dir, n)
        if os.path.exists(p):
            os.remove(p)

