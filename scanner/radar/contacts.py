"""Pull e-mails, phone numbers, contact names and websites out of notice text."""
import re

from .common import latin_digits

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,10}")
INTL_PHONE = re.compile(r"(?<![\w+\-/.])(?:\+|00)\s?\(?\d{1,3}\)?[\s\-./]*\(?\d[\d\s\-./()]{5,16}\d")
KW_PHONE = re.compile(
    r"(?i)(?:tel(?:ephone)?|phone|mobile|mob|cell|whats\s?app|hotline|هاتف|تليفون|تلفون|جوال|موبايل|محمول|واتساب|واتس|"
    r"الرقم الموحد|رقم الهاتف|رقم التواصل)\s*(?:no\.?|number|رقم)?\s*[:.\-]?\s*((?:\+|00)?\(?[\d][\d\s\-./()]{5,20}\d)")
URL = re.compile(r"https?://[^\s<>\"'()\[\]{}]+")
NAME = re.compile(r"(?i)(?:attn\.?|attention|contact person|contact name|focal point|name)\s*[:\-]\s*([^\n,;|]{3,60})")
BAD_TLDS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "pdf", "doc", "docx"}

# mobile prefixes after the country code -> WhatsApp button makes sense
MOBILE = {"20": ("10", "11", "12", "15"), "966": ("5",), "971": ("5",), "974": ("3", "5", "6", "7"),
          "965": ("5", "6", "9"), "973": ("3",), "968": ("7", "9"), "962": ("7",), "970": ("5",),
          "972": ("5",), "963": ("9",), "218": ("9",), "964": ("7",), "967": ("7",)}


def _phone(raw):
    s = latin_digits(raw).strip(" .-/")
    if re.fullmatch(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", s) or re.search(r"\d{4}-\d{1,2}-\d{1,2}", s):
        return None  # a date, not a phone
    digits = re.sub(r"\D", "", s)
    intl = s.startswith("+") or s.startswith("00")
    if s.startswith("00"):
        digits = digits[2:]
    if not (5 <= len(digits) <= 15) or (not intl and len(digits) < 5):
        return None
    if not intl and len(digits) > 12:
        return None
    tel = ("+" + digits) if intl else digits
    wa = ""
    if intl:
        for cc in sorted(MOBILE, key=len, reverse=True):
            if digits.startswith(cc):
                rest = digits[len(cc):].lstrip("0")
                if rest.startswith(MOBILE[cc]) and 8 <= len(rest) <= 10:
                    wa = cc + rest
                break
    return {"display": re.sub(r"\s+", " ", s), "tel": tel, "whatsapp": wa}


def extract(text):
    """Return {'emails': [...], 'phones': [{'display','tel','whatsapp'}], 'websites': [...], 'names': [...]}"""
    text = latin_digits(text or "")
    emails = []
    for e in EMAIL.findall(text):
        e = e.strip(".")
        if e.rsplit(".", 1)[-1].lower() in BAD_TLDS:
            continue
        if e.lower() not in [x.lower() for x in emails]:
            emails.append(e)
    phones, seen = [], set()

    def add(raw, start):
        before = text[max(0, start - 16):start].lower()
        if "fax" in before or "فاكس" in before:
            return
        p = _phone(raw)
        if p and p["tel"].lstrip("+") not in seen:
            seen.add(p["tel"].lstrip("+"))
            phones.append(p)

    for m in KW_PHONE.finditer(text):
        add(m.group(1), m.start())
    for m in INTL_PHONE.finditer(text):
        add(m.group(0), m.start())
    sites = []
    for u in URL.findall(text):
        u = u.rstrip(".,;:")
        if u.rsplit(".", 1)[-1].lower() in BAD_TLDS:
            continue
        if u not in sites:
            sites.append(u)
    names = [n.strip() for n in NAME.findall(text)][:3]
    return {"emails": emails[:8], "phones": phones[:8], "websites": sites[:6], "names": names}
