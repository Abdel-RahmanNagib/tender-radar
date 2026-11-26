"""Tender sources. Every collector returns a list of raw tender dicts (see _tender)."""
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from urllib.parse import quote, urljoin

from .common import XHR_HEADERS, Session, html_to_text, http, http_json, norm, parse_date, pick, q
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


# ------------------------------------------------------------------ Oman – Tender Board (Esnad, public dashboard)
OMAN = "https://etendering.tenderboard.gov.om"
_OMAN_DASH = f"{OMAN}/product/publicDash?viewFlag=NewTenders"
# The portal signs form fields: encparam lists the field names, hashval is SHA-256 of their values joined.
_OMAN_CONSULT_CATS = ("المكاتب الإستشارية", "المكاتب الاستشارية", "أعمال الإستشارات", "أعمال الاستشارات")


def _sha(s):
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def oman_nit_url(nit_id):
    sig = _sha(f"public{nit_id}1RTLfixedrandomno")
    return (f"{OMAN}/product/nitParameterView?mode=public&tenderNo={nit_id}&PublicUrl=1&CTRL_STRDIRECTION=RTL"
            f"&encparam=mode,tenderNo,PublicUrl,CTRL_STRDIRECTION,randomno&hashval={sig}")


def oman_tenderboard(cfg, countries, fetch=None):
    """All tenders open for sale on the Oman Tender Board (about 50 per page, newest first)."""
    if "Oman" not in countries:
        return []
    sess = fetch or Session()
    g, out, seen = _Guard(), [], set()
    first = g.call(sess, _OMAN_DASH)
    if first is None:
        return g.report()
    m = re.search(r'name="hidMax"\s+value="(\d+)"', first)
    last = min(int(m.group(1)) if m else 1, int(cfg.get("pages", 60)))
    pages = [first]
    # Every page also carries a fixed getNit('1') outside the rows, so compare all ids, not the first one.
    first_ids = set(re.findall(r"getNit\('(\d+)'\)", first))
    for page in range(2, last + 1):
        if g.down:
            break
        body = urllib_encode({"securityFlag": "1", "randomno": "fixedrandomno", "CTRL_STRDIRECTION": "RTL",
                              "pageNo": str(page), "newTenderPubpageNo": str(page), "PublicUrl": "1",
                              "viewFlag": "NewTenders", "encparam": "pageNo", "hashval": _sha(str(page))})
        html_page = g.call(sess, _OMAN_DASH, data=body,
                           headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": OMAN,
                                    "Referer": _OMAN_DASH})
        ids = set(re.findall(r"getNit\('(\d+)'\)", html_page or ""))
        if html_page is not None and (not ids or ids <= first_ids):
            break  # the portal answers cloud servers with the first page only; the office PC reads the rest
        if html_page:
            pages.append(html_page)
    for html_page in pages:
        for t in parse_oman(html_page):
            if t["uid"] not in seen:
                seen.add(t["uid"])
                out.append(t)
    return out + g.report()


def urllib_encode(d):
    from urllib.parse import urlencode
    return urlencode(d)


def parse_oman(page):
    """Rows: no. | tender number | name | entity | category [grades] | type [Local/International] |
    dates (Sales EndDate / Bid Closing Date) | fee | bank guarantee | getNit(id)."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        nit = re.search(r"getNit\('(\d+)'\)", row)
        if not nit:
            continue
        tds = re.findall(r"<td([^>]*)>(.*?)</td>", row, re.S | re.I)
        cells = [c for _, c in tds]
        if len(cells) < 8:
            continue
        number = html_to_text(cells[1]).strip()
        tip = re.search(r"Tip\('(.*?)'\)", tds[2][0], re.S)
        full = re.search(r'id="tendDesc\d+"[^>]*value="([^"]*)"', row)
        title = html_to_text(tip.group(1)) if tip else html_to_text(cells[2]).rstrip(". ")
        desc = html_to_text(full.group(1)) if full else ""
        if desc == title:
            desc = ""
        entity = html_to_text(cells[3])
        cat_full = html_to_text(cells[4])
        category = cat_full.split("[")[0].strip()
        ttype = re.sub(r"\s+", " ", html_to_text(cells[5])).strip()
        dates = html_to_text(cells[6])
        close = re.search(r"Closing Date\s*:\s*(\d{1,2}-\d{1,2}-\d{4})", dates)
        sale = re.search(r"Sales EndDate\s*:\s*(\d{1,2}-\d{1,2}-\d{4})", dates)
        fee = html_to_text(cells[7]).strip()
        cat_n = norm(category).replace("ـ", "")
        consult = any(norm(c) in cat_n for c in _OMAN_CONSULT_CATS) or "استشار" in cat_n
        out.append(_tender(
            uid=f"oman:{nit.group(1)}", source_key="oman_tenderboard", source="مجلس المناقصات – سلطنة عمان",
            title=title, description=desc, country="Oman", client=entity, notice_type=ttype or "مناقصة",
            reference=number,
            deadline=parse_date(close.group(1)) if close else None, method=category,
            consulting_flag=consult,
            booklet_price=f"{fee} ريال عماني" if fee and fee.upper() != "N/A" else "",
            url=oman_nit_url(nit.group(1)),
            raw_text=" | ".join(x for x in [title, desc, entity, cat_full, ttype] if x),
            extra=dict(category=cat_full, sales_end=sale.group(1) if sale else "")))
    return out


# ------------------------------------------------------------------ Bahrain – Tender Board (published tenders)
BAHRAIN = "https://www.tenderboard.gov.bh"
_BH_SVC = f"{BAHRAIN}/Templates/TenderBoardWebService.aspx"


def _bh_query(page):
    return ("{'tenderNumber':'','ministry':'0','category':'0', 'tendertype':'0', 'closingDate_filter':'',"
            "'publicTenderOnly':'false','prequalificationOnly':'false','auctionOnly':'false','sortingType':'0',"
            f"'listPage':'mainList', 'Page': '{page}','smeTendersOnly':'false','sectionName':''}}")


def bahrain_tb(cfg, countries, fetch=http):
    if "Bahrain" not in countries:
        return []
    g, out, seen = _Guard(), [], set()
    hdr = {**XHR_HEADERS, "Content-Type": "application/json; charset=utf-8", "Accept": "application/json",
           "Origin": BAHRAIN, "Referer": f"{BAHRAIN}/Tenders/PublicTenders/"}
    raw = g.call(fetch, f"{_BH_SVC}/GetCurrentPublicTenderPageCount", data=_bh_query(-1), headers=hdr)
    try:
        total = int(json.loads(raw)["d"]) if raw else 0
    except (ValueError, KeyError, TypeError):
        total = 0
    today, closed_pages = date.today(), 0
    for page in range(1, min(total or 1, int(cfg.get("pages", 60))) + 1):
        if g.down:
            break
        raw = g.call(fetch, f"{_BH_SVC}/GetCurrentPublicTenderByPage", data=_bh_query(page), headers=hdr)
        if not raw:
            continue
        try:
            fragment = json.loads(raw).get("d", "")
        except ValueError:
            continue
        rows = parse_bahrain(fragment)
        if not rows:
            break
        for t in rows:
            if t["uid"] not in seen:
                seen.add(t["uid"])
                out.append(t)
        # The list runs newest first and keeps closed tenders for months: stop after two closed pages.
        closed_pages = closed_pages + 1 if all(t["deadline"] and t["deadline"] < today for t in rows) else 0
        if closed_pages >= 2:
            break
    return out + g.report()


def parse_bahrain(fragment):
    out = []
    for block in re.split(r'(?=<div data-type=)', fragment)[1:]:
        cols = dict(re.findall(r'<div class="column[^"]*" data-label="([^"]+)">(.*?)</div>(?=<div class="column|</div>|$)',
                               block, re.S))
        subj = cols.get("No./Tender Subject", "")
        link = re.search(r'href="([^"]+)"', subj)
        num = re.search(r"<span>(?:<img[^>]*>)?([^<]*)</span>", subj)
        title = html_to_text(re.sub(r"<span>.*?</span>", " ", subj, flags=re.S))
        if not link or not title:
            continue
        idx = re.search(r"data-index='(\d+)'", block)
        out.append(_tender(
            uid=f"bh:{idx.group(1) if idx else link.group(1)}", source_key="bahrain_tb",
            source="مجلس المناقصات والمزايدات – البحرين", title=title, country="Bahrain",
            client=html_to_text(cols.get("Purchasing Authority", "")),
            notice_type=html_to_text(cols.get("Tender Type", "")) or "Public Tender",
            reference=html_to_text(num.group(1)) if num else "",
            published=parse_date(html_to_text(cols.get("Publish Date", ""))),
            deadline=parse_date(html_to_text(cols.get("Closing Date", ""))),
            url=urljoin(BAHRAIN + "/", html.unescape(link.group(1))),
            raw_text=" | ".join(x for x in [title, html_to_text(cols.get("Purchasing Authority", ""))] if x),
            extra=dict(purchase_before=html_to_text(cols.get("Purchase Before", "")))))
    return out


# ------------------------------------------------------------------ EBRD – client e-procurement portal (ECEPP)
ECEPP = "https://ecepp.ebrd.com/delta"
EBRD_COUNTRIES = {"Egypt": "Egypt", "Jordan": "Jordan", "West Bank And Gaza": "Palestine",
                  "West Bank and Gaza": "Palestine", "Iraq": "Iraq", "Lebanon": "", "Morocco": "", "Tunisia": ""}
_EBRD_OPEN_TYPES = ("invitation for expression interest", "request for proposals", "invitation for prequalification",
                    "invitation for tenders", "general procurement notice")


def ebrd_ecepp(cfg, countries, fetch=http):
    """One page lists every ECEPP notice (about 4 MB); keep open ones in the target countries."""
    g = _Guard(limit=1)
    page = g.call(fetch, f"{ECEPP}/noticeSearchResults.html", timeout=90)
    if page is None:
        return g.report()
    keep_gpn_days = int(cfg.get("general_notice_days", 60))
    return parse_ecepp(page, countries, keep_gpn_days) + g.report()


def parse_ecepp(page, countries, keep_gpn_days=60, today=None):
    today = today or date.today()
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 10:
            continue
        a = re.search(r'href="viewNotice\.html\?displayNoticeId=(\d+)"[^>]*>(.*?)</a>', cells[0], re.S)
        if not a:
            continue
        title = html_to_text(a.group(2))
        country_raw = title.split(":", 1)[0].strip()
        country = EBRD_COUNTRIES.get(country_raw, "")
        if not country or country not in countries:
            continue
        ntype = html_to_text(cells[1])
        state = html_to_text(cells[5])
        published = parse_date(html_to_text(cells[3]))
        deadline = parse_date(html_to_text(cells[4]))
        nlow = ntype.lower()
        if not any(k in nlow for k in _EBRD_OPEN_TYPES):
            continue
        if "general procurement notice" in nlow:
            if not published or (today - published).days > keep_gpn_days:
                continue
        elif state.lower() != "open" and not (deadline and deadline >= today):
            continue
        meta = [x.strip() for x in html_to_text(cells[9]).strip("[] ").split(",")]
        kind = meta[3] if len(meta) > 3 else ""
        out.append(_tender(
            uid=f"ebrd:{a.group(1)}", source_key="ebrd_ecepp", source="البنك الأوروبي لإعادة الإعمار والتنمية (EBRD)",
            title=title.split(":", 1)[-1].strip(), description=html_to_text(cells[2]),
            country=country, client=meta[5] if len(meta) > 5 else "", notice_type=ntype,
            published=published, deadline=deadline, method=meta[4] if len(meta) > 4 else "",
            consulting_flag=kind.lower() == "consultancy",
            url=f"{ECEPP}/viewNotice.html?displayNoticeId={a.group(1)}",
            raw_text=" | ".join(x for x in [title, html_to_text(cells[2]), ", ".join(meta)] if x),
            extra=dict(project=meta[0] if meta else "", project_id=meta[1] if len(meta) > 1 else "",
                       procurement_type=kind, sector=meta[6] if len(meta) > 6 else "", state=state,
                       funding="البنك الأوروبي لإعادة الإعمار والتنمية (EBRD)")))
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


# Development-bank feeds start titles with the notice kind, e.g. "EOI - Egypt - Design of ..." (AfDB).
_FEED_KINDS = [(r"(?:r?eoi|ami|smi)", "Request for Expression of Interest"),
               (r"(?:spn|aoi|aon|ifb|ncb|icb)", "Invitation for Bids"), (r"gpn|avis g[ée]n[ée]ral", "General Procurement Notice"),
               (r"contract awards?|attribution de contrat|avis d.attribution", "Contract Award"),
               (r"ppm|procurement plan|plan de passation", "Procurement Plan")]


def _feed_kind(t):
    m = re.match(r"\s*([^-–]{2,40}?)\s*[-–]\s*([^-–]{2,40}?)\s*[-–]\s*(.+)", t["title"])
    if not m:
        return t
    head = m.group(1).strip().lower()
    for rx, label in _FEED_KINDS:
        if re.fullmatch(rx, head):
            t["notice_type"] = label
            t["country"] = t["country"] or m.group(2).strip()
            break
    return t


def rss_feeds(cfg, countries, fetch=http):
    out = []
    for f in cfg.get("feeds", []):
        url, name = (f, f) if isinstance(f, str) else (f.get("url"), f.get("name", f.get("url")))
        g = _Guard(limit=1)
        out += [_feed_kind(t) for t in parse_rss(g.call(fetch, url, retries=0, timeout=20) or "", name, "rss_feeds")]
        out += g.report()
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


# ------------------------------------------------------------------ UAE – federal entities (MOF Digital Procurement Platform)
UAE_MOF = "https://mof.gov.ae"
_MOF_AJAX = f"{UAE_MOF}/wp-admin/admin-ajax.php"
_MOF_PAGE = f"{UAE_MOF}/en/public-finance/government-procurement/current-business-opportunities/"


def uae_mof(cfg, countries, fetch=http):
    """Current business opportunities of all federal ministries and authorities (9 per page)."""
    if "UAE" not in countries:
        return []
    g, out, seen = _Guard(), [], set()
    hdr = {**XHR_HEADERS, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Origin": UAE_MOF,
           "Referer": _MOF_PAGE}
    for page in range(1, int(cfg.get("pages", 20)) + 1):
        if g.down:
            break
        frag = g.call(fetch, _MOF_AJAX, headers=hdr,
                      data=f"page={page}&search=&ministry=&order=&order_by=&action=mof_dpp_fetch&language=en")
        if frag is None:
            continue
        rows = [t for t in parse_uae_mof(frag) if t["uid"] not in seen]
        if not rows:
            break  # past the last page the portal answers "No results were found"
        for t in rows:
            seen.add(t["uid"])
            out.append(t)
    return out + g.report()


def parse_uae_mof(fragment):
    """Rows: RFQ no. | entity (code) | title | opening date | closing date | link to procurement.gov.ae."""
    out = []
    for row in re.findall(r'<tr[^>]*class="[^"]*mof-table__row[^"]*"[^>]*>(.*?)</tr>', fragment, re.S | re.I):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
        link = re.search(r'href="(https?://[^"]+)"', row)
        if len(cells) < 5 or not link:
            continue
        rfq, entity, title, opens, closes = (html_to_text(c) for c in cells[:5])
        if not rfq or not title:
            continue
        entity = re.sub(r"\s*-\s*\(\d+/\d+\)\s*$", "", entity)
        when = re.search(r"\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M", closes, re.I)
        out.append(_tender(
            uid=f"uaefed:{rfq}", source_key="uae_mof", source="المنصة الرقمية للمشتريات – الجهات الاتحادية (الإمارات)",
            title=title, country="UAE", client=entity, notice_type="Public Tender", reference=rfq,
            published=parse_date(opens), deadline=parse_date(closes),
            deadline_time=re.sub(r":00(?=\s*[AP]M)", "", when.group(0)) if when else "",
            url=html.unescape(link.group(1)), raw_text=" | ".join(x for x in [title, entity] if x),
            submission_line="عبر المنصة الرقمية للمشتريات الاتحادية (procurement.gov.ae) إلكترونياً – بعد التسجيل في سجل الموردين الاتحادي",
            _detail_done=True,  # procurement.gov.ae shows a browser check to scripts; the link works for people
            extra=dict(platform="Digital Procurement Platform (DPP)",
                       links=[{"label": "قائمة الفرص الاتحادية – وزارة المالية", "url": _MOF_PAGE}])))
    return out


# ------------------------------------------------------------------ UAE – Dubai Government eSupply (Jaggaer)
ESUPPLY = "https://esupply.dubai.gov.ae"
_ESUPPLY_GUEST = f"{ESUPPLY}/esop/guest/go/public/opportunity/current"
_ESUPPLY_LIST = f"{ESUPPLY}/esop/toolkit/opportunity/current/list.si"


def esupply_url(opp_id):
    return f"{ESUPPLY}/esop/guest/go/opportunity/detail?opportunityId={opp_id}"


def dubai_esupply(cfg, countries, fetch=None):
    """All current opportunities of the Dubai Government entities (100 per page, guest view)."""
    if "UAE" not in countries:
        return []
    sess = fetch or Session()
    g, out, seen = _Guard(), [], set()
    first = g.call(sess, _ESUPPLY_GUEST)
    if first is None:
        return g.report()
    m = re.search(r"Showing Result\s*\d+\s*-\s*(\d+)\s*of\s*(\d+)", html_to_text(first))
    per, total = (int(m.group(1)), int(m.group(2))) if m else (100, 0)
    last = min(-(-total // max(per, 1)) if total else 1, int(cfg.get("pages", 10)))
    pages = [first]
    for page in range(2, last + 1):
        if g.down:
            break
        html_page = g.call(sess, f"{_ESUPPLY_LIST}?opportunityListManager.pagerComponent.page={page}&userAct=navigation")
        if html_page:
            pages.append(html_page)
    for html_page in pages:
        for t in parse_esupply(html_page):
            if t["uid"] not in seen:
                seen.add(t["uid"])
                out.append(t)
    return out + g.report()


def parse_esupply(page):
    """Rows: no. | currency | buyer | title (goToDetail(id)) | publication | supply category | closing date/time."""
    out = []
    for row in re.findall(r'<tr[^>]*class="[^"]*table_cnt_body[^"]*"[^>]*>(.*?)</tr>', page, re.S | re.I):
        det = re.search(r"goToDetail\((?:&#39;|')(\d+)(?:&#39;|')", row)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
        if not det or len(cells) < 6:
            continue
        link = re.search(r'<a[^>]*class="detailLink"[^>]*>', cells[2]) or re.search(r"<a[^>]*>", cells[2])
        full = re.search(r'title="(?:View Details:\s*)?([^"]*)"', link.group(0)) if link else None
        title = html_to_text(full.group(1)) if full and full.group(1).strip() else html_to_text(cells[2])
        closes = html_to_text(cells[5])
        when = re.search(r"\d{1,2}:\d{2}", closes)
        category = html_to_text(cells[4])
        out.append(_tender(
            uid=f"dxb:{det.group(1)}", source_key="dubai_esupply", source="بوابة حكومة دبي للمشتريات (eSupply)",
            title=title, country="UAE", client=html_to_text(cells[1]), notice_type="Request for Proposal",
            published=parse_date(html_to_text(cells[3])), deadline=parse_date(closes),
            deadline_time=when.group(0) if when else "", url=esupply_url(det.group(1)),
            raw_text=" | ".join(x for x in [title, html_to_text(cells[1])] if x),
            submission_line="عبر بوابة eSupply لحكومة دبي إلكترونياً – بعد تسجيل الشركة كمورد",
            extra=dict(currency=html_to_text(cells[0]), activity="" if category == "Other" else category,
                       opportunity_id=det.group(1),
                       links=[{"label": "كل الفرص الحالية على eSupply", "url": _ESUPPLY_GUEST}])))
    return out


_ESUPPLY_SESSION = []


def _esupply_detail(t, fetch=None):
    """Description, lots and buyer of one opportunity (needs the guest session cookie)."""
    if not getattr(fetch, "keeps_cookies", False):
        if not _ESUPPLY_SESSION:
            sess = Session()
            sess(_ESUPPLY_GUEST, timeout=20, retries=0)
            _ESUPPLY_SESSION.append(sess)
        fetch = _ESUPPLY_SESSION[0]
    oid = t["extra"].get("opportunity_id") or t["uid"].split(":", 1)[1]
    page = fetch(f"{ESUPPLY}/esop/toolkit/opportunity/current/{oid}/detail.si", timeout=20, retries=0)
    _apply_esupply_detail(t, page)
    return t


def parse_esupply_detail(page):
    fields = {}
    for li in re.findall(r'<li[^>]*class="[^"]*FormField[^"]*"[^>]*>(.*?)</li>', page, re.S | re.I):
        label = re.search(r'class="form_question_label"[^>]*>(.*?)</div>', li, re.S | re.I)
        answer = re.search(r'class="form_answer"[^>]*>(.*)$', li, re.S | re.I)
        k = html_to_text(label.group(1)) if label else ""
        v = html_to_text(answer.group(1)) if answer else ""
        if k and v and k not in fields:
            fields[k] = v
    code = re.search(r"<title>\s*Project:\s*([\w-]+)", page)
    lots = [html_to_text(x) for x in re.findall(r'<td class="col__fixed_">(rfq_\d+|tender_\d+|itt_\d+)</td>', page)]
    return {"fields": fields, "code": code.group(1) if code else "", "lots": lots}


def _apply_esupply_detail(t, page):
    d = parse_esupply_detail(page)
    f = d["fields"]
    desc = f.get("Description", "")
    if desc and norm(desc) != norm(t.get("title", "")):
        t["description"] = desc[:1500]
    if f.get("Buyer Organisation"):
        t["client"] = f["Buyer Organisation"]
    if f.get("Closing date/time"):
        t["deadline"] = parse_date(f["Closing date/time"]) or t.get("deadline")
    t["reference"] = d["code"] or t.get("reference", "")
    t["detail_text"] = "\n".join(f"{k}: {v}" for k, v in f.items())[:6000]
    t["raw_text"] = " | ".join(x for x in [t.get("title", ""), desc, f.get("Notes", ""), t.get("client", "")] if x)
    t["extra"].update({k: v for k, v in {"notes": f.get("Notes", "")[:600], "lots": "، ".join(d["lots"][:5]),
                                         "activity": f.get("Supply Category", "") if f.get("Supply Category") != "Other"
                                         else ""}.items() if v})


# ------------------------------------------------------------------ UAE – Abu Dhabi Government Procurement Gate
ADGPG_API = "https://www.adgpg.gov.ae/SCAPI/ADGEs/AlMaqtaa/Tender"
ADGPG_WEB = "https://supplier.adgpg.gov.ae"
_ADGPG_HDR = {"Accept": "application/json, */*", "Origin": ADGPG_WEB, "Referer": f"{ADGPG_WEB}/pages/tender-list.html",
              "Sec-Fetch-Site": "same-site", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"}


def abudhabi_adgpg(cfg, countries, fetch=http):
    """Public tenders of all Abu Dhabi government entities (the portal's public list)."""
    if "UAE" not in countries:
        return []
    g, out, seen = _Guard(), [], set()
    limit, offset, cap = int(cfg.get("page_size", 200)), 0, int(cfg.get("max_items", 1500))
    hdr = {**_ADGPG_HDR, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    while offset < cap and not g.down:
        raw = g.call(fetch, f"{ADGPG_API}/List", headers=hdr,
                     data=f"status=OPEN&offset={offset}&limit={limit}&Category=&Entity=&Sorting=LAST_CREATED"
                          f"&DueDate=&Name=")
        if raw is None:
            break
        try:
            data = json.loads(raw)
        except ValueError:
            break
        items = data.get("TenderList") or []
        for it in items:
            t = adgpg_item(it)
            if t and t["uid"] not in seen:
                seen.add(t["uid"])
                out.append(t)
        offset += len(items)
        if not items or offset >= int(data.get("TenderCount") or 0):
            break
    return out + g.report()


def adgpg_item(it):
    tid = it.get("TenderID")
    name = (it.get("TenderName") or "").strip()
    if not tid or not name:
        return None
    m = re.match(r"\s*(RFQ|RFI|RFP|EOI|RFX|ITT)\s*[-–:]\s*", name, re.I)
    kind = m.group(1).upper() if m else ""
    title = name[m.end():].strip() if m else name
    desc = html_to_text(it.get("TenderDetails") or "")
    ntype = {"RFI": "Request for Information", "EOI": "Expression of Interest", "RFQ": "Request for Quotation",
             "RFP": "Request for Proposal"}.get(kind, "Public Tender")
    return _tender(
        uid=f"adgpg:{tid}", source_key="abudhabi_adgpg", source="بوابة أبوظبي للمشتريات الحكومية (ADGPG)",
        title=title, description="" if norm(desc) == norm(title) else desc[:1500], country="UAE",
        client=(it.get("EntityName") or "").strip(" -"), notice_type=ntype, reference=it.get("TenderNumber") or "",
        published=parse_date(it.get("BiddingOpenDate")), deadline=parse_date(it.get("DueDate")),
        url=f"{ADGPG_WEB}/pages/tender-detail.html?tenderid={tid}",
        raw_text=" | ".join(x for x in [title, desc, it.get("EntityName") or ""] if x),
        submission_line="عبر بوابة أبوظبي للمشتريات الحكومية (ADGPG) إلكترونياً – بعد تسجيل الشركة كمورد",
        extra=dict(tender_id=str(tid), event=kind))


def _adgpg_detail(t, fetch=http):
    raw = fetch(f"{ADGPG_API}/Details/{t['extra'].get('tender_id')}?recommendedLimit=0", headers=_ADGPG_HDR,
                timeout=20, retries=0)
    d = (json.loads(raw) or {}).get("TenderDetails") or {}
    cat_ar, cat_en = d.get("CategoryDescriptionAr") or "", d.get("CategoryDescriptionEn") or ""
    if re.search(r"consult|engineer|architect|advisory|survey|design", cat_en, re.I) or "استشار" in cat_ar:
        t["consulting_flag"] = True
    value = d.get("EstimatedValue") or ""
    if re.fullmatch(r"\D*0\s*-\s*0\D*", value):
        value = ""
    files = len(d.get("Attachments") or [])
    t["extra"].update({k: v for k, v in {"activity": cat_ar or cat_en, "category_en": cat_en if cat_ar else "",
                                         "estimated_value": value, "attachments": f"{files} ملف" if files else ""}.items()
                       if v})
    if d.get("DiscoveryUrl"):
        t["extra"].setdefault("links", []).append({"label": "صفحة المناقصة على نظام أبوظبي (للموردين المسجلين)",
                                                   "url": d["DiscoveryUrl"]})
    if d.get("TenderDetails") and not t.get("description") and norm(d["TenderDetails"]) != norm(t["title"]):
        t["description"] = html_to_text(d["TenderDetails"])[:1500]
    t["detail_text"] = " | ".join(x for x in [t.get("title", ""), t.get("description", ""), cat_en, cat_ar, value] if x)
    return t


# ------------------------------------------------------------------ UAE – Dubai Electricity & Water Authority (DEWA)
DEWA_LIST = "https://www.dewa.gov.ae/en/supplier/services/list-of-tender-documents"


def dewa_tenders(cfg, countries, fetch=http):
    """DEWA open tenders (one page with all floated tenders, fee and closing date)."""
    if "UAE" not in countries:
        return []
    g = _Guard()
    page = g.call(fetch, DEWA_LIST)
    return (parse_dewa(page) if page else []) + g.report()


def parse_dewa(page):
    out = []
    for block in re.split(r'<h2[^>]*class="tender-result__title"[^>]*>', page)[1:]:
        pairs = re.findall(r'<dt[^>]*class="tender-result__key"[^>]*>(.*?)</dt>\s*<dd[^>]*class="tender-result__value"[^>]*>'
                           r'(.*?)</dd>', block, re.S | re.I)
        f = {}
        for k, v in pairs:
            key = re.sub(r"\s*\(.*?\)\s*", " ", html_to_text(k)).strip(" :")
            f.setdefault(key, v)
        number = re.search(r"\d{6,}", html_to_text(f.get("Tender No", "")))
        title = html_to_text(f.get("Name of Tenderer", ""))
        status = html_to_text(f.get("Tender Status", ""))
        if not number or not title or re.search(r"cancel|closed|award", status, re.I):
            continue
        fee = html_to_text(f.get("Tender Fee", ""))
        out.append(_tender(
            uid=f"dewa:{number.group(0)}", source_key="dewa_tenders", source="هيئة كهرباء ومياه دبي (ديوا)",
            title=title, country="UAE", client="Dubai Electricity & Water Authority (DEWA)",
            notice_type="Public Tender", reference=number.group(0),
            published=parse_date(html_to_text(f.get("Floating Date", ""))),
            deadline=parse_date(html_to_text(f.get("Closing Date", ""))),
            booklet_price=f"{fee} درهم إماراتي" if fee and fee not in ("0", "0.00") else "",
            url=DEWA_LIST, raw_text=title,
            submission_line="عبر نظام SRM الخاص بهيئة كهرباء ومياه دبي (srm.dewa.gov.ae) – بعد شراء وثائق المناقصة",
            _detail_done=True,  # one page lists every tender; nothing more per tender without a supplier login
            extra=dict(status=status, links=[{"label": "شراء الوثائق والتقديم – نظام SRM لديوا",
                                              "url": "https://srm.dewa.gov.ae/irj/portal/anonymous"}])))
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
        RELAY_INFO.update(linked=False, label=cfg.get("label", ""))
        return []
    snaps, errors = fetch_snapshots(cfg.get("server", "https://ntfy.sh"), topic, bytes.fromhex(keys[0]),
                                    cfg.get("window", "12h"), get_text=fetch)
    items = {}
    for snap in snaps:
        for it in snap.get("items", []):
            if it.get("uid"):
                items[it["uid"]] = restore_item(it)
    last = snaps[-1] if snaps else {}
    RELAY_INFO.update(linked=True, label=cfg.get("label", ""), last_seen=last.get("ts"), host=last.get("host", ""),
                      sources=last.get("sources", []), snapshots=len(snaps))
    return list(items.values()) + [{"_error": e} for e in errors]


COLLECTORS = {"worldbank": worldbank, "etimad": etimad, "ungm": ungm, "oman_tenderboard": oman_tenderboard,
              "bahrain_tb": bahrain_tb, "ebrd_ecepp": ebrd_ecepp, "uae_mof": uae_mof, "dubai_esupply": dubai_esupply,
              "abudhabi_adgpg": abudhabi_adgpg, "dewa_tenders": dewa_tenders, "monaqasat": monaqasat,
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
    if t["source_key"] in ("dubai_esupply", "abudhabi_adgpg"):
        try:
            if t["source_key"] == "dubai_esupply":
                _esupply_detail(t, fetch)
            else:
                _adgpg_detail(t, fetch)
        except Exception:  # noqa: BLE001
            pass
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
