"""Offline tests (no internet needed):  python scanner/tests/test_scanner.py"""
import json
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from radar import contacts, demo, notify  # noqa: E402
from radar.engine import load_json, run_once  # noqa: E402
from radar.notify import Notifier  # noqa: E402

TODAY = date(2026, 11, 26)
SCANNER = os.path.dirname(HERE)
settings = demo.all_sources_on(load_json(os.path.join(SCANNER, "settings.json")))
profile = demo.demo_profile_overrides(load_json(os.path.join(SCANNER, "profile.json")))


class FakeNotifier(Notifier):
    def __init__(self):
        super().__init__({"console": False}, {}, "https://office.github.io/tender-radar")
        self.tenders, self.summaries = [], []

    def tender(self, rec, today):
        self.tenders.append(rec)
        self.sent += 1

    def summary(self, title, body, click=""):
        self.summaries.append(title)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ✔", msg)


def test_contacts():
    print("contacts extraction")
    c = contacts.extract("Tel: +20 2 0000 1234, Fax: +20 2 0000 9999, Mobile: 00966 50 000 0000, "
                         "E-mail: a.b@example.org; ref PQ-2026-0077 2026-12-14; هاتف: ٠٢٢٣٤٥٦٧٨٩")
    tels = [p["tel"] for p in c["phones"]]
    check("+20200001234" in tels, "international phone found")
    check("+20200009999" not in tels, "fax number ignored")
    check(any(p["whatsapp"] == "966500000000" for p in c["phones"]), "Saudi mobile gets a WhatsApp link")
    check("0223456789" in tels, "Arabic-digit phone after 'هاتف' found")
    check(not any("2026" in p["tel"] for p in c["phones"]), "reference numbers and dates are not phones")
    check(c["emails"] == ["a.b@example.org"], "e-mail found")


def test_full_run():
    print("full scan with sample data")
    tmp = tempfile.mkdtemp()
    fx = demo.fetchers(TODAY)
    n1 = FakeNotifier()
    r1 = run_once(settings, profile, tmp, fetchers=fx, notifier=n1, today=TODAY, log=lambda *a: None)
    titles = [r["title"] for r in r1["new"]]
    by = {r["source_key"] + ":" + r["kind"]: r for r in r1["new"]}
    check(len(r1["new"]) == 15, f"15 suitable opportunities found (got {len(r1['new'])})")
    for bad in ("vehicles", "حاسب", "سفلتة", "furniture", "road safety", "Hydrologist", "industrial area",
                "Hospitality", "Citrix", "UPVC"):
        check(not any(bad in t for t in titles), f"rejected: {bad}")
    check(r1["first_run"] and not n1.tenders and len(n1.summaries) == 1, "first run sends one summary, not a flood")

    wb = by["worldbank:eoi"]
    check(wb["country_ar"] == "مصر" and wb["notice_type_ar"].startswith("طلب إبداء اهتمام"), "WB notice labelled in Arabic")
    check(wb["method_ar"].startswith("الاختيار على أساس الجودة والتكلفة"), "selection method translated")
    ent = wb["contacts"][0]
    check(ent["emails"] == ["pmu.procurement@example.org"] and len(ent["phones"]) == 2, "WB contact: e-mail + 2 phones")
    check(any(p["whatsapp"] for p in ent["phones"]), "mobile number has WhatsApp")
    check(any("shortlisting criteria" in c for c in wb["conditions"]), "shortlisting criteria pulled from the notice")
    check(not any(d["title"].startswith("السير الذاتية") for d in wb["documents"]),
          "CVs not demanded when the notice says experts are not evaluated")
    check(any(d["from_notice"] and "التحالف" in d["title"] for d in wb["documents"]), "JV letter flagged from notice")
    check("الإيميل: pmu.procurement@example.org" in wb["submission_line"], "submission line names the e-mail")

    et = next(r for r in r1["new"] if r["source_key"] == "etimad")
    check(et["booklet_price"] == "1500 ريال" and et["guarantee"] == "مطلوب", "Etimad price and guarantee read")
    check(any(c.get("kind") == "support" and c["phones"][0]["tel"] == "19990" for c in et["contacts"]),
          "Etimad support line 19990 attached")
    check([d["kind"] for d in et["dates"]] == ["published", "inquiry", "deadline", "opening"], "Etimad key dates")
    pq = next(r for r in r1["new"] if r["source_key"] == "etimad_prequal")
    check(any(c.get("kind") == "support" and c["phones"][0]["tel"] == "19990" for c in pq["contacts"]),
          "Etimad prequalification also shows the 19990 support line")

    for r in r1["new"]:
        dl = r.get("deadline")
        dues = [s["due"] for s in r["steps"] if s["due"] and not s["after_deadline"]]
        check(dues == sorted(dues), f"steps in date order: {r['title'][:40]}")
        if dl:
            check(all(d <= dl for d in dues), f"no step after the deadline: {r['title'][:40]}")

    un = by["ungm:rfp"]
    check(un["contacts"][0]["emails"] == ["procurement.gaza@example.org"], "UNGM contact read from the detail page")
    qa = by["monaqasat:rfp"]
    check(qa["contacts"][0]["emails"] == ["procurement@example.qa"], "Qatar e-mail read from tender subject")
    om = next(r for r in r1["new"] if r["source_key"] == "oman_tenderboard")
    check(om["country_ar"] == "عُمان" and "hashval=" in om["links"][0]["url"] and om["deadline"] == (TODAY + timedelta(days=15)).isoformat(),
          "Oman Tender Board: consulting tender with signed notice link and closing date")
    check(not any("حاسب" in r["title"] for r in r1["new"]), "Oman supplies tender rejected")
    bh = next(r for r in r1["new"] if r["source_key"] == "bahrain_tb")
    check(bh["deadline"] == (TODAY + timedelta(days=20)).isoformat() and bh["kind"] == "rfp", "Bahrain tender read with closing date")
    eb = next(r for r in r1["new"] if r["source_key"] == "ebrd_ecepp")
    check(eb["kind"] == "eoi" and eb["country_ar"] == "مصر", "EBRD Egypt EOI read from ECEPP")
    news = by["google_news:news"]
    check(any(link["label"] == "ابحث عن الإعلان الرسمي" for link in news["links"]), "news lead gets a search link")

    uae = {r["source_key"]: r for r in r1["new"] if r["country_ar"] == "الإمارات"}
    check(set(uae) >= {"uae_mof", "dubai_esupply", "abudhabi_adgpg", "dewa_tenders"},
          f"UAE: federal, Dubai, Abu Dhabi and DEWA tenders found ({sorted(uae)})")
    dx = uae["dubai_esupply"]
    check("stormwater drainage tunnels" in dx["summary"] and dx["reference"] == "tender_990101",
          "Dubai eSupply: description and project code read from the opportunity page")
    check(dx["links"][0]["url"].endswith("opportunityId=900101"), "Dubai eSupply: guest link to the opportunity")
    ad = uae["abudhabi_adgpg"]
    check(ad["deadline"] == (TODAY + timedelta(days=14)).isoformat() and "tenderid=7700001" in ad["links"][0]["url"],
          "Abu Dhabi ADGPG: closing date and public tender link")
    check(uae["dewa_tenders"]["booklet_price"].startswith("1050.00"), "DEWA tender fee read")
    check(uae["uae_mof"]["deadline"] == (TODAY + timedelta(days=21)).isoformat(), "UAE federal tender closing date read")

    # second run: nothing new; a changed deadline is followed
    fx2 = demo.fetchers(TODAY)
    orig_wb = fx2["worldbank"]

    def wb2(url, **kw):
        d = orig_wb(url, **kw)
        for n in d["procnotices"]:
            if n["id"] == "OP00999001":
                n["submission_deadline_date"] = (TODAY + timedelta(days=60)).isoformat() + "T00:00:00Z"
        if "project_ctry_name_exact=Libya" in url:
            d["procnotices"].append({"id": "OP00999099", "notice_type": "Request for Expression of Interest",
                                     "noticedate": "25-Nov-2026", "project_ctry_name": "Libya",
                                     "submission_deadline_date": (TODAY + timedelta(days=9)).isoformat(),
                                     "bid_description": "Consulting services for design of roads and drainage in Derna",
                                     "procurement_group": "CS", "contact_email": "derna@example.org"})
        return d
    fx2["worldbank"] = wb2
    n2 = FakeNotifier()
    r2 = run_once(settings, profile, tmp, fetchers=fx2, notifier=n2, today=TODAY, log=lambda *a: None)
    check(len(r2["new"]) == 1 and len(n2.tenders) == 1, "only the new Libya tender is notified on the next run")
    saved = json.load(open(os.path.join(tmp, "tenders.json"), encoding="utf-8"))
    wbr = next(r for r in saved["tenders"] if r["uid"] == "wb:OP00999001")
    check(wbr["deadline"] == (TODAY + timedelta(days=60)).isoformat() and wbr["notes"], "deadline extension recorded")
    st = json.load(open(os.path.join(tmp, "status.json"), encoding="utf-8"))
    check(st["open"] == 16 and all(s["ok"] for s in st["sources"]), f"status file written (open={st['open']})")
    check(os.path.exists(os.path.join(tmp, "profile.json")), "profile for the app written")
    shutil.rmtree(tmp)


def test_notification_payloads():
    print("notification payloads")
    calls = []

    def fake_http(url, data=None, headers=None, **kw):
        calls.append((url, data))
        if "getUpdates" in url:
            return json.dumps({"ok": True, "result": [{"update_id": 7, "message": {"chat": {"id": 555}, "text": "/start"}}]})
        return json.dumps({"ok": True})

    notify.http = fake_http
    state = {}
    n = Notifier({"console": False, "ntfy_topic": "delta-radar-x1", "telegram_token": "T"}, state,
                 "https://office.github.io/tender-radar")
    n.sync_subscribers()
    check(state["telegram_chats"] == ["555"] and state["telegram_offset"] == 8, "Telegram /start subscribes the chat")
    tmp = tempfile.mkdtemp()
    r = run_once(settings, profile, tmp, fetchers=demo.fetchers(TODAY), notifier=FakeNotifier(), today=TODAY,
                 log=lambda *a: None)
    rec = r["new"][0]
    calls.clear()
    n.tender(rec, TODAY)
    ntfy = next(d for u, d in calls if u == "https://ntfy.sh/")
    check(ntfy["topic"] == "delta-radar-x1" and ntfy["click"].endswith("/#t-" + rec["id"]), "ntfy opens the app page")
    check(ntfy["actions"][0]["label"] == "الأوراق والخطوات", "ntfy has a 'documents & steps' button")
    tg = next(d for u, d in calls if "sendMessage" in u)
    check(b"inline_keyboard" in tg, "Telegram message has buttons")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    test_contacts()
    test_full_run()
    test_notification_payloads()
    print("\nALL TESTS PASSED ✔")
