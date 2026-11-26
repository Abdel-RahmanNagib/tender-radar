"""Shared helpers: HTTP, text cleanup, dates. Standard library only (no installs needed)."""
import hashlib
import html
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

_CTX = ssl.create_default_context()
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 TenderRadar/2.0"
TIMEOUT = 25


def http(url, data=None, headers=None, method=None, retries=1, timeout=None):
    """GET/POST and return the body as text. `data` may be a dict (sent as JSON), str or bytes."""
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Language": "ar,en;q=0.8"}
    if headers:
        hdrs.update(headers)
    body = None
    if isinstance(data, (dict, list)):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    elif isinstance(data, str):
        body = data.encode("utf-8")
    elif data is not None:
        body = data
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
            with urllib.request.urlopen(req, timeout=timeout or TIMEOUT, context=_CTX) as r:
                raw = r.read()
                cs = r.headers.get_content_charset() or "utf-8"
                return raw.decode(cs, errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise last


def http_json(url, **kw):
    kw.setdefault("headers", {}).setdefault("Accept", "application/json")
    return json.loads(http(url, **kw))


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v ]+")


def html_to_text(s):
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</tr>|</h\d>|</td>|</th>|</dt>|</dd>", "\n", s)
    s = _TAG.sub(" ", s)
    s = html.unescape(s)
    s = _WS.sub(" ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


_AR_NORM = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "ـ": ""})
_DIACRITICS = re.compile(r"[ً-ْ]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def latin_digits(s):
    return (s or "").translate(_DIGITS)


def norm(s):
    """Lower-case, unify Arabic letter forms, strip diacritics, Latin digits."""
    s = latin_digits((s or "").lower())
    s = _DIACRITICS.sub("", s)
    return s.translate(_AR_NORM)


def pick(d, *keys, default=""):
    """Case-insensitive lookup of the first non-empty key."""
    if not isinstance(d, dict):
        return default
    low = {k.lower(): v for k, v in d.items()}
    for k in keys:
        v = low.get(k.lower())
        if v not in (None, "", [], "0001-01-01T00:00:00"):
            return v
    return default


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_AR_MONTHS = {"يناير": 1, "فبراير": 2, "مارس": 3, "ابريل": 4, "أبريل": 4, "إبريل": 4, "مايو": 5, "يونيو": 6,
              "يوليو": 7, "اغسطس": 8, "أغسطس": 8, "سبتمبر": 9, "اكتوبر": 10, "أكتوبر": 10, "نوفمبر": 11,
              "ديسمبر": 12, "كانون الثاني": 1, "شباط": 2, "آذار": 3, "نيسان": 4, "أيار": 5, "حزيران": 6,
              "تموز": 7, "آب": 8, "أيلول": 9, "تشرين الأول": 10, "تشرين الثاني": 11, "كانون الأول": 12}
AR_MONTH_NAMES = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر",
                  "نوفمبر", "ديسمبر"]
AR_WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def parse_date(v):
    """Best-effort parse of many date formats into a date (None if unknown or Hijri)."""
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = latin_digits(str(v)).strip()
    m = re.match(r"/Date\((\d+)", s)  # .NET JSON date
    if m:
        return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc).date()
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return _safe(y, mo, d) if y > 1700 else None
    m = re.match(r"(\d{1,2})[-/ ]([A-Za-z]{3})[A-Za-z]*\.?[-/ ,]+(\d{4})", s)
    if m:
        return _safe(int(m.group(3)), _MONTHS.get(m.group(2).lower()[:3], 0), int(m.group(1)))
    m = re.match(r"([A-Za-z]{3})[A-Za-z]*\.? (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})", s)
    if m:
        return _safe(int(m.group(3)), _MONTHS.get(m.group(1).lower()[:3], 0), int(m.group(2)))
    m = re.match(r"(\d{1,2})(?:st|nd|rd|th)? (?:of )?([A-Za-z]{3})[A-Za-z]*,? (\d{4})", s)
    if m:
        return _safe(int(m.group(3)), _MONTHS.get(m.group(2).lower()[:3], 0), int(m.group(1)))
    m = re.match(r"(\d{1,2})\s*(?:من\s*)?(" + "|".join(sorted(_AR_MONTHS, key=len, reverse=True)) + r")\s*(\d{4})", s)
    if m:
        return _safe(int(m.group(3)), _AR_MONTHS[m.group(2)], int(m.group(1)))
    m = re.match(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s)
    if m:
        d, mo, y = map(int, m.groups())
        return _safe(y, mo, d) if y > 1700 else None
    try:  # RFC 822 (RSS pubDate)
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).date()
    except Exception:  # noqa: BLE001
        return None


def _safe(y, mo, d):
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def iso(d):
    return d.isoformat() if isinstance(d, (date, datetime)) else (d or None)


def fmt_date_ar(d):
    """date -> 'الأحد 7 ديسمبر 2026'"""
    d = parse_date(d)
    if not d:
        return ""
    return f"{AR_WEEKDAYS[d.weekday()]} {d.day} {AR_MONTH_NAMES[d.month - 1]} {d.year}"


def q(s):
    return urllib.parse.quote_plus(s)


def make_id(uid):
    """Short URL-safe id used in app links (#/t/<id>)."""
    src = re.sub(r"[^a-z0-9]", "", uid.split(":", 1)[0].lower()) or "t"
    return f"{src}-{hashlib.sha1(uid.encode('utf-8')).hexdigest()[:10]}"


def cairo_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Africa/Cairo"))
    except Exception:  # noqa: BLE001  (Windows without tzdata)
        return datetime.now(timezone.utc) + timedelta(hours=2)


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
