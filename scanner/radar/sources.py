"""Tender sources. Every collector returns a list of raw tender dicts (see _tender)."""
import os
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from urllib.parse import quote, urljoin

from .common import XHR_HEADERS, Session, html_to_text, http, http_json, parse_date, pick, q
from .requirements import deadline_from_text, labeled_value

SCANNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Exact country names used by the World Bank procurement API (project_ctry_name_exact).
WB_COUNTRIES = {
    "Egypt": "Egypt, Arab Republic of", "Libya": "Libya", "Syria": "Syrian Arab Republic", "Jordan": "Jordan",
    "Palestine": "West Bank and Gaza", "Saudi Arabia": "Saudi Arabia", "UAE": "United Arab Emirates",
    "Qatar": "Qatar", "Kuwait": "Kuwait", "Bahrain": "Bahrain", "Oman": "Oman", "Yemen": "Yemen, Republic of",
    "Iraq": "Iraq", "MENA (Regional)": "Middle East and North Africa",
}
WB_NOTICE_TYPES = ["Request for Expression of Interest"]


def _tender(**kw):
    t = dict(uid="", source_key="", source="", title="", description="", country="", client="", notice_type="",
             reference="", published=None, deadline=None, deadline_time="", inquiry_deadline=None,
             opening_date=None, method="", method_code="", consulting_flag=False, booklet_price="",
             contact={}, url="", raw_text="", extra={})
    t.update(kw)
    return t


class _Guard:
    """Calls a fetch function; after `limit` failures in a row the source is skipped for this run
    (a hanging portal must never stop the whole scan). Errors are kept for the status page."""

    def __init__(self, limit=2):
        self.fails, self.limit, self.errors = 0, limit, []

    @property
    def down(self):
        return self.fails >= self.limit

    def call(self, fn, url, **kw):
        if self.down:
            return None
        try:
            r = fn(url, **kw)
            self.fails = 0
            return r
        except Exception as e:  # noqa: BLE001
            self.fails += 1
            self.errors.append(f"{url[:90]}: {e}"[:220])
            return None

    def report(self):
        return [{"_error": e} for e in self.errors]


# ------------------------------------------------------------------ World Bank (official API)
def worldbank(cfg, countries, fetch=http_json):
    out, seen, g = [], set(), _Guard()
    rows = int(cfg.get("rows_per_query", 50))
    queries = [(WB_COUNTRIES[c], nt) for c in countries if c in WB_COUNTRIES
               for nt in cfg.get("notice_types", WB_NOTICE_TYPES)]
    for wb_name, ntype in queries:
        if g.down:
            break
        url = ("https://search.worldbank.org/api/v2/procnotices?format=json"
               f"&rows={rows}&os=0&srt=submission_date&order=desc"
               f"&notice_type_exact={quote(ntype, safe='')}&project_ctry_name_exact={quote(wb_name, safe='')}")
        data = g.call(fetch, url)
        if data is None:
            continue
        notices = data.get("procnotices") or []
        if isinstance(notices, dict):
            notices = list(notices.values())
        for n in notices:
            nid = n.get("id")
            if not nid or nid in seen:
                continue
            seen.add(nid)
            text = html_to_text(n.get("notice_text", ""))
            group = n.get("procurement_group", "")
            out.append(_tender(
                uid=f"wb:{nid}", source_key="worldbank", source="البنك الدولي",
                title=n.get("bid_description") or n.get("project_name", ""),
                description=n.get("project_name", ""), country=n.get("project_ctry_name", ""),
                client=n.get("contact_organization", ""), notice_type=n.get("notice_type", ""),
                reference=n.get("bid_reference_no", ""),
                published=parse_date(n.get("noticedate") or n.get("submission_date")),
                deadline=parse_date(n.get("submission_deadline_date")),
                deadline_time=n.get("submission_deadline_time", ""),
                method=n.get("procurement_method_name", ""), method_code=n.get("procurement_method_code", ""),
                consulting_flag=(group == "CS"),
                contact=dict(name=n.get("contact_name", ""), email=n.get("contact_email", ""),
                             phone=n.get("contact_phone_no", ""), org=n.get("contact_organization", ""),
                             address=n.get("contact_address", ""), web=n.get("contact_web_url", "")),
                url=f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{nid}",
                raw_text=text,
                extra=dict(project_id=n.get("project_id", ""), procurement_group=group,
                           funding=f"البنك الدولي – مشروع {n.get('project_id', '')}".strip(" –")),
            ))
    return out + g.report()


# ------------------------------------------------------------------ Etimad – Saudi Arabia
ETIMAD = "https://tenders.etimad.sa"
_ETIMAD_HDR = {**XHR_HEADERS, "Referer": f"{ETIMAD}/Tender/AllTendersForVisitor"}


def _etimad_item(it, kind):
    sid = pick(it, "tenderIdString", "preQualificationIdString", "qualificationIdString", "tenderId", "id")
    if not sid:
        return None
    price = pick(it, "condetionalBookletPrice", "conditionalBookletPrice", "bookletPrice", "buyingCost",
                 "invitationCost", "financialFees")
    activity = pick(it, "tenderActivityName", "activityName", "mainActivityName")
    ttype = pick(it, "tenderTypeName", "tenderType", "qualificationTypeName")
    url = (f"{ETIMAD}/Tender/DetailsForVisitor?STenderId={q(str(sid))}" if kind == "tender"
           else f"{ETIMAD}/Qualification/PrequalificationVisitorDetails/{q(str(sid))}")
    return _tender(
        uid=f"etimad:{sid}" if kind == "tender" else f"etimadpq:{sid}",
        source_key="etimad" if kind == "tender" else "etimad_prequal",
        source="منصة اعتماد – السعودية" if kind == "tender" else "اعتماد – التأهيل المسبق",
        title=pick(it, "tenderName", "preQualificationName", "qualificationName", "name"),
        description=pick(it, "tenderPurpose", "purpose", "description"),
        country="Saudi Arabia",
        client=" – ".join(x for x in [pick(it, "agencyName"), pick(it, "branchName")] if x),
        notice_type=ttype or ("منافسة" if kind == "tender" else "تأهيل مسبق"),
        reference=str(pick(it, "referenceNumber", "tenderNumber", "qualificationNumber")),
        published=parse_date(pick(it, "submitionDate", "submissionDate", "publishDate", "createdAt")),
        deadline=parse_date(pick(it, "lastOfferPresentationDate", "applicationsEndDate", "lastApplicationDate",
                                 "endDate")),
        inquiry_deadline=parse_date(pick(it, "lastEnqueriesDate", "lastEnquiriesDate", "lastInquiryDate")),
        opening_date=parse_date(pick(it, "offersOpeningDate", "offerOpeningDate", "openingDate")),
        method=activity, consulting_flag="استشار" in f"{activity} {ttype}",
        booklet_price=f"{price} ريال" if price not in ("", None, 0, "0") else "",
        url=url, raw_text=" ".join(str(x) for x in [pick(it, "tenderName", "preQualificationName", "name"),
                                                    pick(it, "tenderPurpose", "purpose"), activity, ttype] if x),
        extra=dict(activity=activity),
    )


def etimad(cfg, countries, fetch=http_json):
    if "Saudi Arabia" not in countries:
        return []
    out, seen, g = [], set(), _Guard()
    # TenderCategory=2 = tenders still accepting offers (the portal also lists closed ones).
    # Activity 16 = "المهن الاستشارية" (all consulting tenders); keywords catch consulting work
    # that agencies filed under another activity. The portal returns at most 24 rows per page.
    queries = [f"&TenderActivityId={a}" for a in cfg.get("activity_ids", [16])]
    queries += [f"&MultipleSearch={q(kw)}" for kw in cfg.get("keywords", [])]
    for extra in queries:
        if g.down:
            break
        for page in range(1, int(cfg.get("pages", 3)) + 1):
            url = (f"{ETIMAD}/Tender/AllSupplierTendersForVisitorAsync?IsSearch=true&SortDirection=DESC"
                   f"&Sort=SubmitionDate&TenderCategory=2&PageSize=24&PageNumber={page}{extra}")
            data = g.call(fetch, url, headers=_ETIMAD_HDR)
            items = data.get("data") if isinstance(data, dict) else data
            if not items:
                break
            for it in items:
                t = _etimad_item(it, "tender")
                if t and t["uid"] not in seen:
                    seen.add(t["uid"])
                    out.append(t)
            total = data.get("totalCount") if isinstance(data, dict) else None
            if total is not None and page * 24 >= int(total or 0):
                break
    if cfg.get("prequalifications", True) and not g.down:
        pg = _Guard()
        for kw in cfg.get("prequal_keywords", cfg.get("keywords", [])[:4]):
            data = pg.call(fetch, f"{ETIMAD}/Qualification/AllPreQualificationsAsync?TenderName={q(kw)}"
                                  f"&PageSize=24&pageNumber=1", headers=_ETIMAD_HDR)
            if data is None:
                if pg.down:
                    break
                continue
            items = data.get("data") if isinstance(data, dict) else data
            for it in items or []:
                t = _etimad_item(it, "prequal")
                if t and t["uid"] not in seen:
                    seen.add(t["uid"])
                    out.append(t)
    return out + g.report()


# ------------------------------------------------------------------ Qatar – Monaqasat (public table)
MONAQASAT = "https://monaqasat.mof.gov.qa/TendersOnlineServices/SearchTenders/"


def monaqasat(cfg, countries, fetch=http):
    if "Qatar" not in countries:
        return []
    out, g = [], _Guard()
    for page in range(1, int(cfg.get("pages", 5)) + 1):
        html_page = g.call(fetch, f"{MONAQASAT}{page}")
        if html_page is None:
            if g.down:
                break
            continue
        out += parse_monaqasat(html_page, f"{MONAQASAT}{page}")
    return out + g.report()


def parse_monaqasat(page, page_url):
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells_raw = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
        cells = [html_to_text(c) for c in cells_raw]
        if len(cells) < 8:
            continue
        number, ttype, year, subject, state, ministry, doc_value, bond = cells[1:9]
        if not number.strip().isdigit():
            continue
        if state.strip().lower() not in ("published", "منشورة", "منشور", "open"):
            continue
        href = re.search(r'href="([^"]+)"', row)
        url = urljoin(page_url, href.group(1)) if href else page_url
        out.append(_tender(
            uid=f"monaqasat:{number}/{year}", source_key="monaqasat", source="منصة مناقصات – قطر",
            title=subject, country="Qatar", client=ministry, notice_type=ttype or "Public Tender",
            reference=f"{number}/{year}", booklet_price=doc_value.replace("QAR", "ريال قطري").strip(),
            url=url, raw_text=subject, extra=dict(temporary_insurance=bond)))
    return out


# ------------------------------------------------------------------ UNGM – UN agencies
UNGM = "https://www.ungm.org"
# Country ids used by the UNGM search form.
UNGM_COUNTRY_IDS = {"Bahrain": 2308, "Egypt": 2353, "Iraq": 2389, "Jordan": 2395, "Kuwait": 2401, "Libya": 2408,
                    "Oman": 2446, "Qatar": 2458, "Saudi Arabia": 2471, "Syria": 2490, "UAE": 2505, "Yemen": 2518,
                    "Palestine": 2522}


def ungm(cfg, countries, fetch=None):
    """All open notices in the target countries. The search needs the anti-forgery token that the
    notices page issues together with a cookie, so one session does both requests."""
    sess = fetch or Session()
    g = _Guard()
    page = g.call(sess, f"{UNGM}/Public/Notice")
    if page is None:
        return g.report()
    m = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page)
    token = m.group(1) if m else ""
    ids = [UNGM_COUNTRY_IDS[c] for c in countries if c in UNGM_COUNTRY_IDS]
    as_text = bool(cfg.get("country_ids_as_text"))
    today = date.today().strftime("%d-%b-%Y")
    size = 15  # the portal rejects larger pages (HTTP 400)
    hdr = {**XHR_HEADERS, "Content-Type": "application/json", "RequestVerificationToken": token,
           "Referer": f"{UNGM}/Public/Notice", "Origin": UNGM}
    out, seen = [], set()
    for pi in range(int(cfg.get("pages", 20))):
        body = {"PageIndex": pi, "PageSize": size, "Title": "", "Description": "", "Reference": "",
                "PublishedFrom": "", "PublishedTo": today, "DeadlineFrom": today, "DeadlineTo": "",
                "Countries": [str(i) for i in ids] if as_text else ids, "Agencies": [], "UNSPSCs": [],
                "NoticeTypes": [], "SortField": "DatePublished", "SortAscending": False, "isPicker": False,
                "IsSustainable": False, "IsActive": True, "NoticeDisplayType": None, "TypeOfCompetitions": []}
        html_page = g.call(sess, f"{UNGM}/Public/Notice/Search", data=body, headers=hdr)
        if html_page is None:
            if g.down:
                break
            continue
        rows = parse_ungm(html_page)
        for t in rows:
            if t["uid"] not in seen:
                seen.add(t["uid"])
                out.append(t)
        if len(rows) < size:
            break
    return out + g.report()


_UNGM_ROW = re.compile(r'<div[^>]*\bdata-noticeid="(\d+)"[^>]*class="[^"]*\bdataRow\b[^"]*"[^>]*>', re.I)


def _cell_text(cell_html):
    cell_html = re.sub(r"(?is)<svg.*?</svg>", " ", cell_html)
    cell_html = re.sub(r'(?is)<span[^>]*info-tooltip__text[^>]*>.*?</span>', " ", cell_html)
    return html_to_text(cell_html).replace("\n", " ").strip()


def parse_ungm(page):
    """Rows: options | title | deadline | published | agency | notice type | reference | country."""
    out = []
    marks = list(_UNGM_ROW.finditer(page))
    for i, m in enumerate(marks):
        nid = m.group(1)
        row = page[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(page)]
        cells = [_cell_text(c) for c in re.split(r'(?=<div[^>]*role="cell")', row)[1:]]
        if len(cells) < 8:
            continue
        title, deadline, published, agency, ntype, ref, country = cells[1:8]
        dl = re.match(r"(\d{1,2}-[A-Za-z]{3}-\d{4})\s*([0-9:]{4,5}\s*\([^)]*\))?", deadline)
        out.append(_tender(
            uid=f"ungm:{nid}", source_key="ungm", source=f"الأمم المتحدة – {agency}".strip(" –"), title=title,
            deadline=parse_date(dl.group(1) if dl else deadline), deadline_time=(dl.group(2) or "") if dl else "",
            published=parse_date(published), client=agency, notice_type=ntype, reference=ref, country=country,
            consulting_flag=bool(re.search(r"expression of interest|request for proposal|\beoi\b|\brfp\b", ntype, re.I)),
            url=f"{UNGM}/Public/Notice/{nid}", raw_text=" | ".join([title, ntype, agency, country])))
    return out


# ------------------------------------------------------------------ Kuwait – CAPT (office PC only: blocks cloud IPs)
CAPT = "https://capt.gov.kw/en/tenders/opening-tenders/"


def kuwait_capt(cfg, countries, fetch=http):
    if "Kuwait" not in countries:
        return []
    out, seen, g = [], set(), _Guard()
    for page in range(1, int(cfg.get("pages", 5)) + 1):
        url = f"{CAPT}?page={page}"
        html_page = g.call(fetch, url)
        if html_page is None:
            if g.down:
                break
            continue
        items = parse_capt(html_page, url)
        if not items:
            break
        for t in items:
            if t["uid"] not in seen:
                seen.add(t["uid"])
                out.append(t)
    return out + g.report()


def parse_capt(page, page_url):
    """Each tender is a block of <ul><li>Label</li><li>Value</li></ul> pairs starting with 'Tender no.'."""
    out = []
    for chunk in re.split(r"<li>\s*Tender no\.?\s*</li>", page)[1:]:
        first = re.match(r"\s*<li>(.*?)</li>", chunk, re.S)
        number = html_to_text(first.group(1)) if first else ""
        stop = chunk.find("</table>")
        body = chunk[: stop if stop > 0 else 6000][:6000]
        f = {html_to_text(a).lower().strip(" :"): html_to_text(b)
             for a, b in re.findall(r"<ul>\s*<li>(.*?)</li>\s*<li>(.*?)</li>\s*</ul>", body, re.S)}
        subject = f.get("tender subject", "")
        if not number or not subject:
            continue
        out.append(_tender(
            uid=f"capt:{number}", source_key="kuwait_capt", source="الجهاز المركزي للمناقصات العامة – الكويت",
            title=subject, country="Kuwait", client=f.get("organisation", f.get("organization", "")),
            notice_type=f.get("bidding type", "") or "مناقصة عامة", reference=number,
            published=parse_date(f.get("request date", "")), deadline=parse_date(f.get("last date", "")),
            booklet_price=f.get("price", "").replace("KWD", "دينار كويتي").strip(),
            url=page_url, raw_text=" | ".join(x for x in [subject, f.get("organisation", ""), number] if x),
            extra=dict(temporary_insurance=f.get("insurance", ""))))
    return out


# ------------------------------------------------------------------ RSS (Google News + custom feeds)
def parse_rss(xml_text, source, source_key, max_age_days=None):
    out = []
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError:
        return out
    cutoff = date.today() - timedelta(days=max_age_days) if max_age_days else None
    atom = "{http://www.w3.org/2005/Atom}"
    entries = list(root.iter("item")) or list(root.iter(atom + "entry"))
    for it in entries:
        g = lambda tag: (it.findtext(tag) or it.findtext(atom + tag) or "").strip()  # noqa: E731
        link = g("link")
        if not link:
            le = it.find(atom + "link")
            link = le.get("href", "") if le is not None else ""
        pub = parse_date(g("pubDate") or g("published") or g("updated"))
        if cutoff and pub and pub < cutoff:
            continue
        src = it.find("source")
        desc = html_to_text(g("description") or g("summary"))
        out.append(_tender(
            uid=f"rss:{link}", source_key=source_key,
            source=source + (f" – {src.text}" if src is not None and src.text else ""),
            title=html_to_text(g("title")), description=desc, published=pub,
            notice_type="News lead" if source_key == "google_news" else "Portal listing", url=link, raw_text=desc))
    return out


def google_news(cfg, countries, fetch=http):
    out, seen, g = [], set(), _Guard()
    age = int(cfg.get("max_age_days", 7))
    feeds = [(x, "hl=ar&gl=EG&ceid=EG:ar") for x in cfg.get("queries_ar", [])] + \
            [(x, "hl=en&gl=AE&ceid=AE:en") for x in cfg.get("queries_en", [])]
    for query, loc in feeds:
        if g.down:
            break
        url = f"https://news.google.com/rss/search?q={q(query + f' when:{age}d')}&{loc}"
        for t in parse_rss(g.call(fetch, url) or "", "أخبار الطروحات", "google_news", age):
            key = re.sub(r"\W+", "", t["title"].lower())[:80]
            if key not in seen:
                seen.add(key)
                out.append(t)
    return out + g.report()


def rss_feeds(cfg, countries, fetch=http):
    out = []
    for f in cfg.get("feeds", []):
        url, name = (f, f) if isinstance(f, str) else (f.get("url"), f.get("name", f.get("url")))
        g = _Guard(limit=1)
        out += parse_rss(g.call(fetch, url, retries=0, timeout=20) or "", name, "rss_feeds") + g.report()
    return out


# ------------------------------------------------------------------ official tender pages (generic)
_A = re.compile(r'<a\s[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', re.S | re.I)


def web_pages(cfg, countries, fetch=http):
    out = []
    for p in cfg.get("pages", []):
        if p.get("country") and p["country"] not in countries:
            continue
        try:
            page = fetch(p["url"], retries=0, timeout=20)
        except Exception as e:  # noqa: BLE001  one portal down must not stop the rest
            out.append({"_error": f"{p['name']}: {e}"[:220]})
            continue
        for href, text in _A.findall(page):
            text = html_to_text(text)
            if len(text) < 20 or href.startswith(("javascript:", "mailto:", "tel:")):
                continue
            link = urljoin(p["url"], href)
            out.append(_tender(uid=f"web:{link}", source_key="web_pages", source=p["name"], title=text,
                               country=p.get("country", ""), notice_type="Portal listing", url=link, raw_text=text))
    return out


# ------------------------------------------------------------------ office-PC helper (relay)
RELAY_INFO = {}


def pc_relay(cfg, countries, fetch=http):
    """Tenders the office-PC helper found on portals that refuse cloud servers (signed, via ntfy)."""
    from .relay import fetch_snapshots, restore_item
    RELAY_INFO.clear()
    topic = cfg.get("topic")
    keyfile = os.path.join(SCANNER_DIR, cfg.get("public_key_file", "pc_public_key.txt"))
    if not topic:
        return []
    keys = re.findall(r"\b[0-9a-fA-F]{64}\b", open(keyfile, encoding="utf-8").read()) if os.path.exists(keyfile) else []
    if not keys:
        RELAY_INFO.update(linked=False)
        return []
    snaps, errors = fetch_snapshots(cfg.get("server", "https://ntfy.sh"), topic, bytes.fromhex(keys[0]),
                                    cfg.get("window", "12h"), get_text=fetch)
    items = {}
    for snap in snaps:
        for it in snap.get("items", []):
            if it.get("uid"):
                items[it["uid"]] = restore_item(it)
    last = snaps[-1] if snaps else {}
    RELAY_INFO.update(linked=True, last_seen=last.get("ts"), host=last.get("host", ""),
                      sources=last.get("sources", []), snapshots=len(snaps))
    return list(items.values()) + [{"_error": e} for e in errors]


COLLECTORS = {"worldbank": worldbank, "etimad": etimad, "ungm": ungm, "monaqasat": monaqasat,
              "kuwait_capt": kuwait_capt, "pc_relay": pc_relay, "google_news": google_news,
              "rss_feeds": rss_feeds, "web_pages": web_pages}


# ------------------------------------------------------------------ detail pages (only for matches)
ETIMAD_LABELS = {
    "purpose": ["الغرض من المنافسة", "الغرض من التأهيل"],
    "contract_duration": ["مدة العقد"],
    "submission_method": ["طريقة تقديم العروض"],
    "initial_guarantee": ["مطلوب ضمان الإبتدائي", "مطلوب ضمان الابتدائي", "الضمان الابتدائي"],
    "guarantee_address": ["عنوان الضمان الإبتدائي", "عنوان الضمان الابتدائي"],
    "final_guarantee": ["الضمان النهائي"],
    "insurance": ["هل التأمين من متطلبات المنافسة"],
    "booklet_value": ["قيمة وثائق المنافسة"],
}


def fetch_detail(t, fetch=http):
    """Open the notice page and add text, deadline and Etimad fields. Never raises."""
    url = t.get("url", "")
    if not url.startswith("http") or "news.google." in url or t["source_key"] == "worldbank":
        return t
    try:
        page = fetch(url, timeout=15, retries=0)
    except Exception:  # noqa: BLE001
        return t
    text = html_to_text(page)[:25000]
    t["detail_text"] = text
    if not t.get("deadline"):
        t["deadline"] = deadline_from_text(text)
    if t["source_key"] == "monaqasat":
        _apply_monaqasat_detail(t, page)
    if t["source_key"] in ("etimad", "etimad_prequal"):
        found = {k: labeled_value(text, labs) for k, labs in ETIMAD_LABELS.items()}
        t["extra"].update({k: v for k, v in found.items() if v})
        if found.get("purpose") and not t.get("description"):
            t["description"] = found["purpose"]
        if found.get("submission_method"):
            t["submission_line"] = "عبر منصة اعتماد – " + found["submission_method"]
        if found.get("booklet_value") and not t.get("booklet_price"):
            t["booklet_price"] = found["booklet_value"]
    return t


def parse_monaqasat_detail(page):
    """Qatar tender page: header/value tables, the activity list and the special conditions."""
    out = {"fields": {}, "activities": [], "conditions": {}}
    for tb in re.findall(r"<table[^>]*>(.*?)</table>", page, re.S | re.I):
        thead = re.search(r"<thead[^>]*>(.*?)</thead>", tb, re.S | re.I)
        heads = [html_to_text(x) for x in re.findall(r"<th[^>]*>(.*?)</th>", thead.group(1), re.S | re.I)] if thead else []
        tbody = re.search(r"<tbody[^>]*>(.*?)</tbody>", tb, re.S | re.I)
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody.group(1) if tbody else tb, re.S | re.I)
        cells = [[html_to_text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S | re.I)] for r in rows]
        low = [h.lower() for h in heads]
        if low[:2] == ["activity code", "activity name"]:
            out["activities"] += [(c[0], c[1]) for c in cells if len(c) >= 2]
        elif low[:2] == ["name", "value"]:
            out["conditions"].update({c[0]: c[1] for c in cells if len(c) >= 2})
        elif heads and cells and len(cells[0]) == len(heads):
            out["fields"].update({h: v for h, v in zip(heads, cells[0]) if v})
    return out


def _apply_monaqasat_detail(t, page):
    d = parse_monaqasat_detail(page)
    f = d["fields"]
    t["deadline"] = parse_date(f.get("Closing Date")) or t.get("deadline")
    if f.get("Brief Description"):
        t["description"] = f["Brief Description"]
    req = f.get("Request Types", "")
    acts = d["activities"]
    engineering = any(code.startswith("711") or re.search(r"engineer|architect|consult|survey|design", name, re.I)
                      for code, name in acts)
    t["consulting_flag"] = bool(t.get("consulting_flag") or re.search(r"consult", req, re.I) or engineering)
    names = "، ".join(name for _, name in acts[:6])
    t["extra"].update({k: v for k, v in {"activities": names, "request_types": req,
                                         "target": f.get("Targeted Tenderer Type", ""),
                                         "contract_duration": d["conditions"].get("Contract Duration", "")}.items() if v})
    t["raw_text"] = " | ".join(x for x in [t.get("title", ""), f.get("Brief Description", ""), req, names] if x)
