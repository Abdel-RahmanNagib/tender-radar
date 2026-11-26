"""Turn a raw tender into the clear record the app and the notifications show."""
import re
from urllib.parse import quote_plus

from . import contacts
from .common import fmt_date_ar, iso, make_id
from .knowledge import (COUNTRIES, DOCS, INQUIRY_HOW, SUPPORT, build_steps, detect_kind, method_ar,
                        notice_documents, notice_type_ar)
from .requirements import extract_requirements, submission_line

_REGION_CC = ("20", "966", "971", "974", "965", "973", "968", "962", "970", "963", "218", "964", "967")
_SKIP_SITES = ("projects.worldbank.org", "google.com", "news.google", "ungm.org/Public/Notice", "etimad.sa/Tender")


def _entity_phone(raw):
    """WB phone numbers often come without '+': add it when they start with a regional country code."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not raw.strip().startswith(("+", "00")) and len(digits) >= 10 and digits.startswith(_REGION_CC):
        raw = "+" + digits
    return contacts._phone(raw)


def _contacts(t, kind, country):
    c = t.get("contact") or {}
    text = "\n".join(x for x in [t.get("raw_text", ""), t.get("detail_text", "")] if x)
    found = contacts.extract(text)
    emails = [c["email"]] if c.get("email") else []
    emails += [e for e in found["emails"] if e.lower() not in [x.lower() for x in emails]]
    phones = []
    p = _entity_phone(c.get("phone", ""))
    if p:
        phones.append(p)
    for ph in found["phones"]:
        if ph["tel"].lstrip("+")[-9:] not in [x["tel"].lstrip("+")[-9:] for x in phones]:
            phones.append(ph)
    sites = [c["web"]] if c.get("web") else []
    sites += [s for s in found["websites"] if not any(k in s for k in _SKIP_SITES) and s not in sites]
    entity = {
        "title": "جهة التعاقد – للاستفسار عن المشروع",
        "name": c.get("name") or (found["names"][0] if found["names"] else ""),
        "org": c.get("org") or t.get("client", ""),
        "emails": emails[:5], "phones": phones[:5], "address": c.get("address", ""),
        "website": sites[0] if sites else "",
    }
    if kind == "etimad":
        entity["note"] = "الاستفسارات تُرسل من تبويب «الاستفسارات» داخل صفحة المنافسة على منصة اعتماد."
    elif not (entity["emails"] or entity["phones"]):
        entity["note"] = "لم تُذكر أرقام أو إيميلات في البيانات المتاحة — افتح الإعلان الرسمي لمعرفة جهة التواصل."
    out = [entity]
    src = "etimad" if (t.get("source_key") or "").startswith("etimad") else t.get("source_key")
    sup = SUPPORT.get(src) or (None if src in ("worldbank", "ungm") else SUPPORT.get(country))
    if sup:
        s = dict(sup)
        s["phones"] = [contacts._phone(x) for x in sup.get("phones", []) if contacts._phone(x)]
        s["kind"] = "support"
        out.append(s)
    return out


def _documents(kind, t, text):
    docs = [{"title": a, "detail": b, "from_notice": False} for a, b in DOCS[kind]]
    for label, key in notice_documents(text):
        hit = [d for d in docs if key in d["title"] or key in d["detail"]]
        if hit:
            hit[0]["from_notice"] = True
        else:
            docs.append({"title": label, "detail": "مطلوب حسب نص الإعلان.", "from_notice": True})
    return docs


def build_record(t, info, today, now_iso):
    kind = detect_kind(t)
    country = info.get("country") or t.get("country", "")
    country_ar, flag = COUNTRIES.get(country, (country, ""))
    text = "\n".join(x for x in [t.get("raw_text", ""), t.get("detail_text", "")] if x)
    sub = t.get("submission_line") or submission_line(text)
    if sub and not sub.startswith("عبر"):
        sub = f"طريقة التسليم كما وردت في الإعلان: «{sub}»"
    c0 = t.get("contact") or {}
    if sub and c0.get("email") and kind in ("eoi", "gpn", "rfp"):
        sub += f" – الإيميل: {c0['email']}"
    t["submission_line"] = sub
    steps = build_steps(kind, t, today)
    title = (t.get("title") or "").strip()
    summary = (t.get("description") or "").strip()
    if not summary or summary == title:
        body = (t.get("detail_text") or t.get("raw_text") or "").replace(title, "").strip()
        summary = body[:320].rsplit(" ", 1)[0] + (" …" if len(body) > 320 else "") if body else ""
    dates = []
    for label, d, k in [("تاريخ النشر", t.get("published"), "published"),
                        ("آخر موعد للاستفسارات", t.get("inquiry_deadline"), "inquiry"),
                        ("آخر موعد للتقديم", t.get("deadline"), "deadline"),
                        ("فتح العروض", t.get("opening_date"), "opening")]:
        if d:
            dates.append({"label": label, "date": iso(d), "date_ar": fmt_date_ar(d), "kind": k,
                          "time": t.get("deadline_time", "") if k == "deadline" else ""})
    links = [{"label": "فتح الإعلان الرسمي", "url": t["url"]}] if t.get("url") else []
    ex = t.get("extra") or {}
    if ex.get("project_id"):
        links.append({"label": "صفحة المشروع الممول",
                      "url": f"https://projects.worldbank.org/en/projects-operations/project-detail/{ex['project_id']}"})
    links += [x for x in ex.get("links") or [] if x.get("url") and x["url"] != t.get("url")]
    if kind == "news":
        links.append({"label": "ابحث عن الإعلان الرسمي",
                      "url": "https://www.google.com/search?q=" + quote_plus(title + " مناقصة")})
    doc_note = ""
    if "not be evaluated at the shortlisting" in text.lower():
        doc_note = "حسب الإعلان: السير الذاتية للخبراء لا تُقيَّم في مرحلة القائمة المختصرة — تُطلب لاحقاً في مرحلة العروض."
    return {
        "id": make_id(t["uid"]), "uid": t["uid"], "first_seen": now_iso, "updated": now_iso,
        "source_key": t.get("source_key", ""), "source": t.get("source", ""), "kind": kind,
        "notice_type": t.get("notice_type", ""), "notice_type_ar": notice_type_ar(t.get("notice_type", ""),
                                                                                  t.get("source_key", "")),
        "title": title, "is_arabic": bool(re.search(r"[؀-ۿ]", title)), "summary": summary,
        "country": country, "country_ar": country_ar, "flag": flag, "client": t.get("client", ""),
        "reference": t.get("reference", ""), "published": iso(t.get("published")), "deadline": iso(t.get("deadline")),
        "deadline_time": t.get("deadline_time", ""), "inquiry_deadline": iso(t.get("inquiry_deadline")),
        "opening_date": iso(t.get("opening_date")),
        "method": t.get("method", ""),
        "method_ar": "" if kind == "etimad" else method_ar(t.get("method", ""), t.get("method_code", "")),
        "activity": ex.get("activity", ""),
        "funding": ex.get("funding", ""), "booklet_price": t.get("booklet_price", ""),
        "guarantee": {"نعم": "مطلوب", "لا": "غير مطلوب"}.get((ex.get("initial_guarantee") or "").strip(),
                                                               ex.get("initial_guarantee") or ex.get("temporary_insurance", "")),
        "contract_duration": ex.get("contract_duration", ""),
        "match": {"level": info.get("level", "low"), "level_ar": info.get("level_ar", "محتمل"),
                  "score": info.get("score", 0), "disciplines": [ar for _, ar in info["disciplines"]],
                  "ids": [i for i, _ in info["disciplines"]]},
        "dates": dates, "contacts": _contacts(t, kind, country), "inquiry_how": INQUIRY_HOW[kind],
        "documents": _documents(kind, t, text), "conditions": extract_requirements(text), "doc_note": doc_note,
        "submission_line": sub, "steps": steps, "links": links, "excerpt": text[:2500],
        "notes": [],
    }


def refresh_steps(rec, today):
    """Re-compute step dates (used when a deadline changes)."""
    from .common import parse_date
    t = {"deadline": parse_date(rec.get("deadline")), "inquiry_deadline": parse_date(rec.get("inquiry_deadline")),
         "opening_date": parse_date(rec.get("opening_date")), "submission_line": rec.get("submission_line", ""),
         "booklet_price": rec.get("booklet_price", "")}
    rec["steps"] = build_steps(rec["kind"], t, today)
    rec["dates"] = [d for d in rec.get("dates", []) if d["kind"] != "deadline"]
    if t["deadline"]:
        rec["dates"].append({"label": "آخر موعد للتقديم", "date": rec["deadline"],
                             "date_ar": fmt_date_ar(t["deadline"]), "kind": "deadline",
                             "time": rec.get("deadline_time", "")})
