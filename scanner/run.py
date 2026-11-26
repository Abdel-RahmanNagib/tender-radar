#!/usr/bin/env python3
"""رادار المناقصات الاستشارية – المحرك

  python scanner/run.py              فحص واحد الآن
  python scanner/run.py --loop       فحص مستمر (كل check_every_minutes دقيقة)
  python scanner/run.py --app        فتح التطبيق على هذا الكمبيوتر (أضف --loop للفحص المستمر)
  python scanner/run.py --test       إرسال إشعار تجريبي (للتأكد من ntfy / تيليجرام / الإيميل)
  python scanner/run.py --demo       بيانات تجريبية لتجربة التطبيق بدون إنترنت
"""
import argparse
import os
import sys
import time
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from radar import demo  # noqa: E402
from radar.engine import channels_from, load_json, reset_data, run_once  # noqa: E402
from radar.notify import Notifier  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = os.path.join(ROOT, "app", "data")


def _is_demo_data():
    try:
        return bool(load_json(os.path.join(DATA, "tenders.json")).get("demo"))
    except (OSError, ValueError):
        return False


def main():
    ap = argparse.ArgumentParser(description="Tender Radar")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--app", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--serve-only", action="store_true", help="open the app without scanning")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    settings = load_json(os.path.join(HERE, "settings.json"))
    profile = load_json(os.path.join(HERE, "profile.json"))

    if a.demo:
        reset_data(DATA)
        today = date.today()
        run_once(demo.all_sources_on(settings), demo.demo_profile_overrides(profile), DATA,
                 fetchers=demo.fetchers(today), today=today,
                 notifier=Notifier({"console": False}, {}), app_url="")
        demo.mark_demo(DATA)
        print("✔ تم تجهيز بيانات تجريبية في app/data — افتح التطبيق بالأمر: python scanner/run.py --app")
        return

    if a.test:
        today = date.today()
        tmp = os.path.join(ROOT, "app", "data", "_test")
        reset_data(tmp)
        n = Notifier({"console": False}, {})
        r = run_once(settings, demo.demo_profile_overrides(profile), tmp, fetchers=demo.fetchers(today),
                     today=today, notifier=n, app_url="")
        rec = r["new"][0] if r["new"] else None
        notifier = Notifier(channels_from(settings), {}, os.environ.get("APP_URL", ""))
        notifier.sync_subscribers()
        if rec:
            rec["title"] = "🧪 إشعار تجريبي – " + rec["title"]
            notifier.tender(rec, today)
        print("القنوات:", {k: bool(v) for k, v in notifier.ch.items() if k in ("ntfy_topic", "telegram_token")},
              "| أخطاء:", notifier.errors or "لا يوجد")
        return

    if a.app or a.serve_only:
        from radar.server import serve
        _, url = serve(os.path.join(ROOT, "app"), a.port, open_browser=not a.no_browser)
        print(f"التطبيق يعمل على: {url}  (اتركه مفتوحاً – لإيقافه أغلق النافذة)")
        if a.serve_only:
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                return

    if _is_demo_data():
        reset_data(DATA)  # never mix sample data with real tenders

    interval = max(15, int(settings.get("check_every_minutes", 60)))
    while True:
        print(f"\n[{datetime.now():%Y-%m-%d %H:%M}] جاري الفحص…", flush=True)
        try:
            run_once(settings, profile, DATA)
        except Exception as e:  # noqa: BLE001  never die in loop mode
            print("تعذر الفحص:", e, flush=True)
        if not a.loop:
            break
        time.sleep(interval * 60)
        settings = load_json(os.path.join(HERE, "settings.json"))
    if a.app and not a.loop:
        print("الفحص انتهى. التطبيق ما زال مفتوحاً — اضغط Ctrl+C للإغلاق.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
