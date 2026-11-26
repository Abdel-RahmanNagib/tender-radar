"""Read the notice text: conditions to apply, how/where to submit, and dates written in the text."""
import re

from .common import latin_digits, norm, parse_date

CUES = [
    "shortlist", "short-list", "criteria", "qualification", "qualified", "experience", "similar",
    "eligib", "key experts", "key staff", "cv", "curriculum", "must", "shall", "required", "require",
    "submit", "submission", "deliver", "delivered", "deadline", "documents", "registration", "association",
    "joint venture", "sub-consultan", "conflict of interest", "terms of reference", "bid security",
    "guarantee", "language", "selection method", "years",
    "يجب", "شروط", "الشروط", "المستندات", "الوثائق", "المؤهلات", "الخبرة", "خبرات", "مشاريع مماثلة",
    "التأهيل", "التصنيف", "السجل التجاري", "الضمان", "كراسة", "كراسه", "آخر موعد", "اخر موعد", "تقديم العروض",
    "العرض الفني", "العرض المالي", "الشهادات", "الزكاة", "التأمينات", "الغرفة التجارية", "هيئة المهندسين",
]
_CUES = [norm(c) for c in CUES]
_STRONG = ("shortlist", "criteria", "يجب", "شروط", "deadline", "must be", "eligib")


def sentences(text):
    return [s.strip(" -•\t") for s in re.split(r"(?<=[.!؟?])\s+(?=[A-Zء-ي(])|\n+", text or "")]


def extract_requirements(text, limit=8, max_len=480):
    """Sentences that describe what the consultant must have or submit."""
    picked, seen = [], set()
    for s in sentences(text):
        if len(s) < 35:
            continue
        ns = norm(s)
        hits = sum(1 for c in _CUES if c in ns)
        if hits >= 2 or (hits == 1 and any(k in ns for k in _STRONG)):
            key = ns[:60]
            if key in seen:
                continue
            seen.add(key)
            picked.append(s if len(s) <= max_len else s[:max_len].rsplit(" ", 1)[0] + " …")
        if len(picked) >= limit:
            break
    return picked


_SUBMIT = re.compile(r"(?i)(must be (?:delivered|submitted|sent|received)|should be (?:delivered|submitted|sent)|"
                     r"submitted (?:to|by|through|via|electronically)|delivered (?:to|by|in)|"
                     r"تقدم العروض|يتم تقديم|تسلم العروض|ترسل العروض|يتم إرسال|عن طريق البوابة)")


def submission_line(text):
    for s in sentences(text):
        if _SUBMIT.search(s) and 25 < len(s) < 420:
            return s.rstrip(".")
    return ""


_DEADLINE_KW = re.compile(
    r"(?i)(deadline|closing date|closing time|due date|submission date|not later than|no later than|on or before|"
    r"آخر موعد|اخر موعد|موعد أقصاه|موعد اقصاه|تاريخ الإغلاق|تاريخ الاغلاق|تاريخ إغلاق|قبل تاريخ)")
_DATE_IN = re.compile(
    r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Za-z]{3,9},?\s+\d{4}|"
    r"[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|\d{1,2}\s*(?:من\s*)?[ء-ي]{3,7}\s*\d{4}|"
    r"\d{1,2}-[A-Za-z]{3}-\d{4})")


def deadline_from_text(text):
    """First date written right after a 'deadline' keyword."""
    t = latin_digits(text or "")
    for m in _DEADLINE_KW.finditer(t):
        window = t[m.end():m.end() + 90]
        d = _DATE_IN.search(window)
        if d:
            parsed = parse_date(d.group(1))
            if parsed:
                return parsed
    return None


def labeled_value(text, labels, max_len=140):
    """For portal pages laid out as 'label\\nvalue' – return the value after the first label found."""
    lines = [ln.strip() for ln in (text or "").split("\n")]
    for i, ln in enumerate(lines):
        for lab in labels:
            if lab in ln:
                rest = ln.split(lab, 1)[1].strip(" :：-")
                if not rest and i + 1 < len(lines):
                    rest = lines[i + 1]
                if rest:
                    return rest[:max_len]
    return ""
