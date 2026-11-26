"""Tender sources. Every collector returns a list of raw tender dicts (see _tender)."""
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from urllib.parse import urljoin

from .common import html_to_text, http, http_json, parse_date, pick, q
from .requirements import deadline_from_text, labeled_value

WB_COUNTRIES = {
    "Egypt": "Egypt", "Libya": "Libya", "Syria": "Syrian Arab Republic", "Jordan": "Jordan",
    "Palestine": "West Bank and Gaza", "Saudi Arabia": "Saudi Arabia", "UAE": "United Arab Emirates",
    "Qatar": "Qatar", "Kuwait": "Kuwait", "Bahrain": "Bahrain", "Oman": "Oman", "Yemen": "Yemen",
    "Iraq": "Iraq", "MENA (Regional)": "Middle East and North Africa",
}


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
    rows = int(cfg.get("rows_per_query", 100))
    for name in countries:
        wb_name = WB_COUNTRIES.get(name)
        if not wb_name:
            continue
        url = ("https://search.worldbank.org/api/v2/procnotices?format=json"
               f"&rows={rows}&os=0&srt=submission_date&order=desc&qterm={q(wb_name)}")
        data = g.call(fetch, url)
        if data is None:
            if g.down:
                break
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
_ETIMAD_HDR = {"X-Requested-With": "XMLHttpRequest", "Referer": f"{ETIMAD}/Tender/AllTendersForVisitor"}


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
    for kw in cfg.get("keywords", [""]):
        if g.down:
            break
        for page in range(1, int(cfg.get("pages", 2)) + 1):
            url = (f"{ETIMAD}/Tender/AllSupplierTendersForVisitorAsync?IsSearch=true&SortDirection=DESC"
                   f"&Sort=SubmitionDate&PageSize={cfg.get('page_size', 24)}&PageNumber={page}"
                   f"&MultipleSearch={q(kw)}")
            data = g.call(fetch, url, headers=_ETIMAD_HDR)
            items = data.get("data") if isinstance(data, dict) else data
            if not items:
                break
            for it in items:
                t = _etimad_item(it, "tender")
                if t and t["uid"] not in seen:
                    seen.add(t["uid"])
                    out.append(t)
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
def ungm(cfg, countries, fetch=http):
    out, seen, g = [], set(), _Guard()
    for kw in cfg.get("keywords", [""]):
        if g.down:
            break
        body = {"PageIndex": 0, "PageSize": int(cfg.get("page_size", 50)), "Title": kw, "Description": "",
                "Reference": "", "PublishedFrom": "", "PublishedTo": "", "DeadlineFrom": "", "DeadlineTo": "",
                "Countries": [], "Agencies": [], "UNSPSCs": [], "NoticeTypes": [], "SortField": "DatePublished",
                "SortAscending": False, "isPicker": False, "IsSustainable": False, "IsActive": True,
                "NoticeDisplayType": None, "NoticeSearchTotalLabelId": "noticeSearchTotal",
                "TypeOfCompetitions": []}
        page = g.call(fetch, "https://www.ungm.org/Public/Notice/Search", data=body,
                      headers={"X-Requested-With": "XMLHttpRequest"})
        for t in parse_ungm(page or ""):
            if t["uid"] not in seen:
                seen.add(t["uid"])
                out.append(t)
    return out + g.report()


def parse_ungm(page):
    out = []
    for m in re.finditer(r'data-noticeid="(\d+)"(.*?)(?=data-noticeid="|\Z)', page, re.S):
        nid, block = m.group(1), m.group(2)
        cells = [html_to_text(c) for c in re.findall(r'class="[^"]*tableCell[^"]*"[^>]*>(.*?)</div>', block, re.S)]
        cells = [c for c in cells if c]
        get = lambda i: cells[i] if len(cells) > i else ""  # noqa: E731
        out.append(_tender(
            uid=f"ungm:{nid}", source_key="ungm", source="بوابة مشتريات الأمم المتحدة UNGM", title=get(0),
            deadline=parse_date(get(1)), published=parse_date(get(2)), client=get(3), notice_type=get(4),
            reference=get(5), country=get(6), url=f"https://www.ungm.org/Public/Notice/{nid}",
            raw_text=" | ".join(cells)))
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


COLLECTORS = {"worldbank": worldbank, "etimad": etimad, "monaqasat": monaqasat, "ungm": ungm,
              "google_news": google_news, "rss_feeds": rss_feeds, "web_pages": web_pages}


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
