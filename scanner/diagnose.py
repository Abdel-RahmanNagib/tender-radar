#!/usr/bin/env python3
"""Diagnostics (run on GitHub: Actions -> Diagnose).

1. Matching: why collected tenders were rejected, per source, with samples.
2. Reachability: for portals that fail from the cloud, try other header/TLS settings.
Writes a Markdown report to the job summary and to stdout. Changes nothing.
"""
import collections
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from radar.common import norm  # noqa: E402
from radar.engine import load_json  # noqa: E402
from radar.scoring import Matcher  # noqa: E402
from radar.sources import COLLECTORS  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = []


def w(line=""):
    OUT.append(line)
    print(line, flush=True)


def esc(s, n=110):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return (s[:n] + "…" if len(s) > n else s).replace("|", "/")


def parts(m, t):
    title = norm(t.get("title", "") + " " + t.get("description", ""))
    body = norm(t.get("raw_text", "")[:8000])
    d_title = [ar for _, ar, _, p in m.disciplines if m._hits(title, p)]
    d_body = [ar for _, ar, _, p in m.disciplines if not m._hits(title, p) and m._hits(body, p)]
    c_title = m._hits(title, m.consult)
    c_body = m._hits(body, m.consult)
    return d_title, d_body, c_title, c_body


def matching():
    settings = load_json(os.path.join(HERE, "settings.json"))
    profile = load_json(os.path.join(HERE, "profile.json"))
    countries = settings.get("countries") or list(profile["countries"])
    today = date.today()
    m_low = Matcher(profile, "low")
    w("## 1. Matching on real data")
    w(f"Date: {today} — min level in settings: `{settings.get('min_level')}`")
    for name in ("worldbank", "etimad", "ungm", "oman_tenderboard", "bahrain_tb", "ebrd_ecepp", "google_news",
                 "web_pages"):
        t0 = time.time()
        try:
            items = COLLECTORS[name](profile["sources"].get(name, {}), countries)
        except Exception as e:  # noqa: BLE001
            w(f"\n### {name}: ERROR {e}")
            continue
        errs = [i["_error"] for i in items if "_error" in i]
        items = [i for i in items if "_error" not in i]
        reasons, levels, rows = collections.Counter(), collections.Counter(), []
        for t in items:
            ok, info = m_low.evaluate(t, today)
            if ok:
                levels[info.get("level")] += 1
                reasons["ACCEPTED at " + info.get("level", "")] += 1
            else:
                r = info.get("reason", "")
                reasons[re.sub(r"\d+", "N", r)] += 1
            rows.append((t, ok, info))
        w(f"\n### {name}: {len(items)} items, {len(errs)} failed requests, {time.time() - t0:.0f}s")
        for r, n in reasons.most_common():
            w(f"- {n} × {r}")

        if name == "etimad":
            act = collections.Counter(t.get("extra", {}).get("activity", "") for t in items)
            w("\n**Etimad activity (top 15):**")
            for a, n in act.most_common(15):
                w(f"- {n} × {esc(a, 80)}")
            open_items = [x for x in rows if not (x[0].get("deadline") and x[0]["deadline"] < today)]
            w(f"\nOpen (deadline not passed or unknown): {len(open_items)}")
        if name == "worldbank":
            nt = collections.Counter((t.get("notice_type", ""), "CS" if t.get("consulting_flag") else "-")
                                     for t in items)
            w("\n**World Bank notice types (type, CS?):**")
            for (a, b), n in nt.most_common(12):
                w(f"- {n} × {esc(a, 60)} / {b}")
            open_cs = [x for x in rows if x[0].get("consulting_flag")
                       and not (x[0].get("deadline") and x[0]["deadline"] < today)]
            w(f"\n**Open World Bank consulting notices: {len(open_cs)}**")
            w("| ok | level/reason | country | title | disc. title | disc. body |")
            w("|---|---|---|---|---|---|")
            for t, ok, info in open_cs[:60]:
                d_t, d_b, _, _ = parts(m_low, t)
                w(f"| {'✅' if ok else '—'} | {esc(info.get('level') or info.get('reason'), 40)} | "
                  f"{esc(t.get('country'), 20)} | {esc(t.get('title'), 90)} | {esc(', '.join(d_t), 40)} | "
                  f"{esc(', '.join(d_b), 40)} |")
            continue

        if name == "web_pages":
            by = collections.defaultdict(list)
            for t in items:
                by[t.get("source")].append(t)
            w("\n**Links per portal (first 6 texts):**")
            for src, lst in by.items():
                w(f"- **{esc(src, 50)}** ({len(lst)}): " + " · ".join(esc(x.get('title'), 50) for x in lst[:6]))
            continue

        def table(title, sel, limit=30):
            sel = sel[:limit]
            if not sel:
                return
            w(f"\n**{title} ({len(sel)} shown)**")
            w("| level/reason | score | title | disc. title | consult title |")
            w("|---|---|---|---|---|")
            for t, ok, info in sel:
                d_t, d_b, c_t, c_b = parts(m_low, t)
                w(f"| {esc(info.get('level') or info.get('reason'), 45)} | {info.get('score', '')} | "
                  f"{esc(t.get('title'), 95)} | {esc(', '.join(d_t), 35)} | {esc(', '.join(c_t[:3]), 35)} |")

        openr = [x for x in rows if not (x[0].get("deadline") and x[0]["deadline"] < today)]
        table("Accepted (any level)", [x for x in openr if x[1]], 40)
        table("Rejected: discipline in title but not consulting",
              [x for x in openr if not x[1] and "استشارية" in x[2].get("reason", "")], 25)
        table("Rejected: consulting words in title but no discipline",
              [x for x in openr if not x[1] and "تخصصات" in x[2].get("reason", "") and parts(m_low, x[0])[2]], 25)
        table("Rejected: low score", [x for x in openr if not x[1] and "درجة" in x[2].get("reason", "")], 20)


# --------------------------------------------------------------------------- reachability
CHROME = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
    "Sec-Ch-Ua-Mobile": "?0", "Sec-Ch-Ua-Platform": '"Windows"',
}


def ctx_default():
    return ssl.create_default_context()


def ctx_tls12():
    c = ssl.create_default_context()
    c.maximum_version = ssl.TLSVersion.TLSv1_2
    return c


def probe(url, headers, ctx, data=None, extra=None):
    h = dict(headers)
    if extra:
        h.update(extra)
    t0 = time.time()
    try:
        req = urllib.request.Request(url, data=data, headers=h)
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            body = r.read(400000).decode("utf-8", "replace")
            title = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
            rows = len(re.findall(r"<tr", body, re.I))
            return f"{r.status} {len(body)}B rows={rows} {esc(title.group(1) if title else body[:60], 50)} ({time.time() - t0:.1f}s)"
    except urllib.error.HTTPError as e:
        srv = e.headers.get("Server", "") if e.headers else ""
        cf = " cloudflare" if (e.headers and (e.headers.get("cf-ray") or "cloudflare" in srv.lower())) else ""
        return f"HTTP {e.code} server={esc(srv, 25)}{cf} ({time.time() - t0:.1f}s)"
    except Exception as e:  # noqa: BLE001
        return f"ERR {esc(e, 80)} ({time.time() - t0:.1f}s)"


def reachability():
    w("\n## 2. Reachability of blocked portals from GitHub")
    ungm_body = json.dumps({"PageIndex": 0, "PageSize": 15, "Title": "", "Description": "", "Reference": "",
                            "PublishedFrom": "", "PublishedTo": "", "DeadlineFrom": "", "DeadlineTo": "",
                            "Countries": [], "Agencies": [], "UNSPSCs": [], "NoticeTypes": [], "SortField": "DatePublished",
                            "SortAscending": False, "isPicker": False, "IsSustainable": False,
                            "NoticeDisplayType": None, "NoticeSearchTotalLabelId": "noticeSearchTotal",
                            "TypeOfCompetitions": []}).encode()
    bh = ("{'tenderNumber':'','ministry':'0','category':'0', 'tendertype':'0', 'closingDate_filter':'',"
          "'publicTenderOnly':'false','prequalificationOnly':'false','auctionOnly':'false','sortingType':'0',"
          "'listPage':'mainList', 'Page': '-1','smeTendersOnly':'false','sectionName':''}").encode()
    targets = [
        ("Qatar Monaqasat", "https://monaqasat.mof.gov.qa/TendersOnlineServices/SearchTenders/1", None, None),
        ("Kuwait CAPT", "https://capt.gov.kw/en/tenders/opening-tenders/", None, None),
        ("Oman Tender Board", "https://etendering.tenderboard.gov.om/product/publicDash?viewFlag=NewTenders", None,
         None),
        ("Bahrain Tender Board", "https://www.tenderboard.gov.bh/Templates/TenderBoardWebService.aspx/"
                                 "GetCurrentPublicTenderPageCount", bh,
         {"Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest"}),
        ("EBRD ECEPP", "https://ecepp.ebrd.com/delta/noticeSearchResults.html", None, None),
        ("UNGM page", "https://www.ungm.org/Public/Notice", None, None),
        ("AfDB", "https://www.afdb.org/en/projects-and-operations/procurement", None, None),
    ]
    variants = [("chrome-headers", CHROME, ctx_default), ("chrome+tls1.2", CHROME, ctx_tls12)]
    w("| portal | " + " | ".join(v[0] for v in variants) + " |")
    w("|---|" + "---|" * len(variants))
    for name, url, data, extra in targets:
        cells = [probe(url, hdr, mk(), data, extra) for _, hdr, mk in variants]
        w(f"| {name} | " + " | ".join(cells) + " |")


def main():
    t0 = time.time()
    w("# Tender Radar – diagnostics")
    try:
        reachability()
    except Exception as e:  # noqa: BLE001
        w(f"reachability failed: {e}")
    try:
        matching()
    except Exception as e:  # noqa: BLE001
        w(f"matching failed: {e}")
    w(f"\n_Done in {time.time() - t0:.0f}s_")
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
