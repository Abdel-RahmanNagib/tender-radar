"""Decide whether a tender is something a design/supervision consultancy can apply for."""
import re
from datetime import date

from .common import norm
from .knowledge import LEVEL_MIN, LEVELS


class Matcher:
    def __init__(self, profile, min_level="medium", skip_expired=True):
        self.countries = {c: [self._rx(k) for k in kws] for c, kws in profile["countries"].items()}
        self.disciplines = [(d["id"], d["ar"], d["weight"], [self._rx(k) for k in d["keywords"]])
                            for d in profile["disciplines"]]
        self.consult = [self._rx(k) for k in profile["consultancy_terms"]]
        self.negative = [self._rx(k) for k in profile["negative_terms"]]
        self.works_only = [self._rx(k) for k in profile.get("works_terms", [])]
        self.excluded_types = [norm(x) for x in profile.get("excluded_notice_types", [])]
        self.min_score = LEVEL_MIN.get(min_level, 7)
        self.skip_expired = skip_expired

    @staticmethod
    def _rx(word):
        w = norm(word)
        if re.search(r"[a-z0-9]", w):  # Latin: whole word / phrase
            return (word, re.compile(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])"))
        # Arabic: whole word with optional prefixes (و ب ف ل ك + ال/لل) and common suffixes.
        # Short stems (<=4 letters) must end at a word boundary so "الري" does not hit "الرياض".
        stem = w[2:] if w.startswith("ال") and len(w) > 4 else w
        left = r"(?<![ء-ي])(?:[وبفلك])?(?:ال|لل)?"
        core = r"\s+".join(re.escape(p) for p in stem.split())
        right = r"(?:ات|ه|يه|ين|ون|ي)?(?![ء-ي])" if len(stem.replace(" ", "")) <= 4 else ""
        return (word, re.compile(left + core + right))

    @staticmethod
    def _hits(text, pats):
        return [w for w, rx in pats if rx.search(text)]

    def detect_country(self, t):
        if t.get("country"):
            base = norm(t["country"])
            for c, pats in self.countries.items():
                if self._hits(base, pats):
                    return c
        text = norm(" ".join([t.get("title", ""), t.get("description", ""), t.get("client", ""),
                              t.get("raw_text", "")[:3000]]))
        best, n = "", 0
        for c, pats in self.countries.items():
            k = len(self._hits(text, pats))
            if k > n:
                best, n = c, k
        return best

    def evaluate(self, t, today=None):
        """Return (accepted, info). info: country, score, level, level_ar, disciplines[(id, ar)], reason."""
        today = today or date.today()
        info = {"disciplines": [], "reason": "", "score": 0}
        ntype = norm(t.get("notice_type", ""))
        if any(x and x in ntype for x in self.excluded_types):
            info["reason"] = "إعلان ترسية أو إلغاء"
            return False, info
        if self.skip_expired and t.get("deadline") and t["deadline"] < today:
            info["reason"] = "انتهى موعده"
            return False, info
        country = self.detect_country(t)
        info["country"] = country
        if not country:
            info["reason"] = "خارج الدول المستهدفة"
            return False, info

        title = norm(t.get("title", "") + " " + t.get("description", ""))
        body = norm(t.get("raw_text", "")[:8000])
        meta = norm(" ".join([t.get("method", ""), t.get("method_code", ""), t.get("notice_type", "")]))
        if "individual" in meta or "indv" in meta or "individual consultant" in title or "استشاري فرد" in title:
            info["reason"] = "مخصص لاستشاري فرد وليس لمكتب"
            return False, info

        score, in_title, in_body = 0, 0, 0
        for did, ar, w, pats in self.disciplines:
            th, bh = self._hits(title, pats), self._hits(body, pats)
            if th or bh:
                score += w if th else max(1, w // 2)
                in_title += 1 if th else 0
                in_body += 0 if th else 1
                info["disciplines"].append((did, ar))
        if t.get("direct_invite"):
            # An invitation e-mailed to the office's registered supplier account is always shown:
            # the portal already filtered it by the categories the office registered for.
            info["score"] = score = max(score + 4, 9)
            info["level"], info["level_ar"] = next((k, lab) for thr, k, lab in LEVELS if score >= thr)
            return True, info
        if not info["disciplines"] or (in_title == 0 and in_body < 2):
            info["reason"] = "لا يطابق تخصصات المكتب"
            return False, info

        consult_title = self._hits(title, self.consult)
        consult_any = consult_title or self._hits(body, self.consult)
        structured = bool(t.get("consulting_flag")) or "expression of interest" in meta or "استشار" in meta
        if not (structured or consult_title or (consult_any and t.get("source_key") in ("worldbank", "ungm"))):
            info["reason"] = "ليست خدمات استشارية (تنفيذ أو توريد)"
            return False, info
        score += 4 if consult_title else (2 if consult_any else 0)
        score += 3 if structured else 0
        if self._hits(title, self.negative):
            score -= 6
        if self._hits(title, self.works_only) and not consult_title:
            score -= 4
        if t.get("source_key") in ("google_news", "web_pages", "rss_feeds"):
            score -= 1  # unverified leads rank a little lower
        info["score"] = score
        for threshold, key, label in LEVELS:
            if score >= threshold:
                info["level"], info["level_ar"] = key, label
                break
        if score < self.min_score:
            info["reason"] = f"درجة الملاءمة {score} أقل من الحد {self.min_score}"
            return False, info
        return True, info
