"""Arabic labels, official support contacts, required documents and ordered application steps.

Support contacts below were checked against official pages (Nov 2026). Each entry keeps its source
so the app can show where the number came from. Only verified numbers are listed; for other
portals the app links to the official site instead of guessing a number.
"""
from datetime import timedelta

from .common import fmt_date_ar, norm

COUNTRIES = {  # key -> (Arabic name, flag)
    "Egypt": ("مصر", "🇪🇬"), "Libya": ("ليبيا", "🇱🇾"), "Syria": ("سوريا", "🇸🇾"),
    "Jordan": ("الأردن", "🇯🇴"), "Palestine": ("فلسطين", "🇵🇸"), "Saudi Arabia": ("السعودية", "🇸🇦"),
    "UAE": ("الإمارات", "🇦🇪"), "Qatar": ("قطر", "🇶🇦"), "Kuwait": ("الكويت", "🇰🇼"),
    "Bahrain": ("البحرين", "🇧🇭"), "Oman": ("عُمان", "🇴🇲"), "Yemen": ("اليمن", "🇾🇪"),
    "Iraq": ("العراق", "🇮🇶"), "MENA (Regional)": ("إقليمي – الشرق الأوسط", "🌍"),
}

SOURCES = {
    "worldbank": "البنك الدولي",
    "etimad": "منصة اعتماد – السعودية",
    "etimad_prequal": "اعتماد – التأهيل المسبق",
    "ungm": "بوابة مشتريات الأمم المتحدة UNGM",
    "monaqasat": "منصة مناقصات – قطر",
    "google_news": "أخبار الطروحات",
    "rss_feeds": "خلاصات RSS",
    "web_pages": "بوابات حكومية وبنوك تنمية",
}

NOTICE_TYPES = [  # (contains, Arabic label) – first match wins
    ("expression of interest", "طلب إبداء اهتمام (EOI)"),
    ("expressions of interest", "طلب إبداء اهتمام (EOI)"),
    ("general procurement notice", "إعلان مشتريات عام (GPN)"),
    ("prequalification", "دعوة للتأهيل المسبق"),
    ("pre-qualification", "دعوة للتأهيل المسبق"),
    ("request for proposal", "طلب عروض (RFP)"),
    ("invitation for bids", "دعوة لتقديم عطاءات"),
    ("request for bids", "دعوة لتقديم عطاءات"),
    ("request for quotation", "طلب أسعار (RFQ)"),
    ("public tender", "مناقصة عامة"),
    ("limited tender", "مناقصة محدودة"),
    ("news lead", "خبر عن طرح – يحتاج تأكيد"),
    ("portal listing", "إعلان على بوابة رسمية"),
]

METHODS = {
    "qcbs": "الاختيار على أساس الجودة والتكلفة (QCBS)",
    "qbs": "الاختيار على أساس الجودة فقط (QBS)",
    "cqs": "الاختيار على أساس مؤهلات الاستشاري (CQS)",
    "lcs": "الاختيار على أساس أقل تكلفة (LCS)",
    "fbs": "الاختيار بميزانية ثابتة (FBS)",
    "sss": "اختيار مباشر من مصدر واحد (SSS)",
    "dir": "تعاقد مباشر",
}

LEVELS = [(11, "high", "مناسب جداً"), (7, "medium", "مناسب"), (4, "low", "محتمل")]
LEVEL_MIN = {"high": 11, "medium": 7, "low": 4}

# ------------------------------------------------------------------ official support channels
SUPPORT = {
    "etimad": {
        "title": "الدعم الفني لمنصة اعتماد (وزارة المالية السعودية)",
        "phones": ["19990"], "emails": ["ccc@mof.gov.sa"],
        "website": "https://portal.etimad.sa/ar-sa/aboutetimad/contactuscrm",
        "hours": "24 ساعة طوال أيام الأسبوع",
        "note": "للتسجيل والمشاكل التقنية فقط. أسئلة المنافسة نفسها تُرسل من تبويب «الاستفسارات» داخل صفحة المنافسة.",
        "source": "دليل استقبال الشكاوى – اعتماد، وصفحة الدعم بوزارة المالية",
    },
    "ungm": {
        "title": "دعم بوابة UNGM",
        "website": "https://help.ungm.org/hc/en-us",
        "note": "لا يوجد رقم هاتف؛ التواصل عبر نموذج «Contact UNGM» في مركز المساعدة. أسئلة المناقصة تُرسل لجهة التواصل في الإعلان.",
        "source": "مركز المساعدة UNGM",
    },
    "Bahrain": {
        "title": "مجلس المناقصات والمزايدات – البحرين (الدعم الفني)",
        "phones": ["+973 1756 6666"], "emails": ["helpdesk@tenderboard.gov.bh", "info@tenderboard.gov.bh"],
        "website": "https://etendering.tenderboard.gov.bh",
        "hours": "الأحد–الأربعاء 7:00–14:15، الخميس 7:00–14:00",
        "source": "بوابة المناقصات الإلكترونية – البحرين",
    },
    "Oman": {
        "title": "دعم بوابة المناقصات الإلكترونية – عُمان",
        "phones": ["+968 2440 2244"], "emails": ["Etenderhd@ptlc.gov.om"],
        "website": "https://etendering.tenderboard.gov.om",
        "note": "للمشاكل التقنية في البوابة.",
        "source": "كما تنشره إعلانات الجهات العُمانية (مثل عُمران)",
    },
    "Qatar": {
        "title": "منصة مناقصات – وزارة المالية القطرية",
        "website": "https://monaqasat.mof.gov.qa",
        "note": "كثير من الإعلانات تذكر إيميل الجهة للاستفسار داخل وصف المناقصة نفسها.",
    },
    "Egypt": {
        "title": "بوابة التعاقدات العامة – مصر",
        "website": "https://etenders.gov.eg",
        "note": "بيانات التواصل مع الجهة الطارحة تظهر في صفحة العملية الشرائية على البوابة.",
    },
    "Jordan": {"title": "نظام الشراء الإلكتروني الأردني JONEPS", "website": "https://www.joneps.gov.jo"},
    "Kuwait": {"title": "الجهاز المركزي للمناقصات العامة – الكويت", "website": "https://capt.gov.kw"},
    "Palestine": {"title": "بوابة الشراء العام – فلسطين", "website": "https://www.shiraa.gov.ps"},
    "UAE": {"title": "بوابات المشتريات الحكومية – الإمارات",
            "website": "https://www.adgpg.gov.ae",
            "note": "أبوظبي: ADGPG – دبي: esupply.dubai.gov.ae – الجهات الاتحادية والمحلية لها بوابات خاصة."},
}

# ------------------------------------------------------------------ required documents
DOCS = {
    "eoi": [
        ("خطاب إبداء الاهتمام", "موقّع ومختوم من المفوَّض بالتوقيع، موجّه لجهة التواصل، ويذكر اسم المهمة ورقمها المرجعي."),
        ("الملف التعريفي للمكتب", "سنة التأسيس، الفروع، عدد المهندسين، التخصصات، والبرامج المستخدمة."),
        ("جدول المشاريع المماثلة", "آخر 10 سنوات: اسم المشروع، العميل، الدولة، القيمة، المدة، ونطاق عملكم تحديداً."),
        ("شهادات إنجاز أو خطابات العملاء", "لأهم المشاريع المماثلة إن وُجدت."),
        ("المستندات القانونية", "السجل التجاري أو ترخيص المكتب الاستشاري، وشهادة القيد بنقابة المهندسين أو الهيئة المختصة."),
        ("القدرات الفنية والإدارية", "الهيكل التنظيمي، عدد الفنيين، البرامج (Civil 3D، InfoWorks/SWMM، HEC-RAS، WaterGEMS، BIM)، وشهادات ISO إن وُجدت."),
        ("خطاب التحالف أو الاستشاري الفرعي", "فقط إذا ستتقدمون مع شريك: يحدد الشريك ونوع الشراكة (JV أو Sub-consultant)."),
        ("إقرار الأهلية وعدم تعارض المصالح", "حسب قواعد الجهة الممولة."),
    ],
    "gpn": [
        ("خطاب تسجيل اهتمام عام", "يُرسل لوحدة إدارة المشروع لطلب إدراجكم في قائمة المراسلة للمهام الاستشارية القادمة."),
        ("الملف التعريفي للمكتب", "مع ملخص المشاريع المماثلة."),
    ],
    "rfp": [
        ("وثائق الطرح (الكراسة / RFP)", "تنزيلها أو شراؤها من الجهة أو البوابة، والاحتفاظ بإيصال الشراء."),
        ("العرض الفني", "فهم المهمة، المنهجية وخطة العمل، البرنامج الزمني، والهيكل التنظيمي للفريق."),
        ("السير الذاتية للخبراء الرئيسيين", "موقّعة، مع خطابات التفرغ والالتزام."),
        ("جدول المشاريع المماثلة وشهادات العملاء", "مرتبطة بنطاق المهمة."),
        ("العرض المالي", "في ملف أو مظروف منفصل حسب نموذج الجهة."),
        ("ضمان العطاء / الضمان الابتدائي", "إذا نصّت عليه الوثائق — ابدأ إجراءات البنك مبكراً."),
        ("المستندات القانونية وتفويض التوقيع", "السجل التجاري، الترخيص، شهادة القيد، وتوكيل المفوَّض بالتوقيع."),
    ],
    "etimad": [
        ("حساب المنشأة على منصة اعتماد", "مفعّل ومحدّث: سجل تجاري سعودي أو ترخيص فرع أجنبي من وزارة الاستثمار."),
        ("إيصال شراء كراسة الشروط", "من صفحة المنافسة على المنصة."),
        ("تصنيف المكتب الهندسي", "اعتماد المكتب لدى الهيئة السعودية للمهندسين."),
        ("الشهادات السارية", "الزكاة والضريبة، التأمينات الاجتماعية، الغرفة التجارية، نطاقات (السعودة)، وشهادة ضريبة القيمة المضافة."),
        ("العرض الفني", "حسب متطلبات الكراسة ومعايير التقييم."),
        ("العرض المالي", "غالباً في ملف منفصل عن العرض الفني (نظام المظروفين)."),
        ("الضمان الابتدائي", "إذا نصّت عليه الكراسة — قيمته وعنوانه في تفاصيل المنافسة."),
    ],
    "portal": [
        ("التسجيل في بوابة الجهة أو الدولة", "كمكتب استشاري — بعض الدول تشترط ترخيصاً محلياً أو شريكاً محلياً."),
        ("وثائق الطرح", "شراء أو تنزيل الكراسة والاحتفاظ بالإيصال."),
        ("ملف التأهيل", "الملف التعريفي + المشاريع المماثلة + التراخيص."),
        ("العرض الفني والعرض المالي", "حسب نماذج الجهة."),
        ("الضمان الابتدائي", "إذا طُلب."),
    ],
    "news": [
        ("تأكيد الإعلان الرسمي أولاً", "هذا خبر منشور عن طرح؛ تأكد من الإعلان الرسمي لدى الجهة قبل البدء."),
        ("ملف التأهيل العام جاهزاً", "الملف التعريفي + المشاريع المماثلة + التراخيص، لحين صدور الوثائق."),
    ],
}

# documents the notice text itself asks for (detected by keywords): (keywords, label, key to find it in DOCS)
NOTICE_DOCS = [
    (["curriculum vitae", "cvs", "cv ", "key experts", "key staff", "السير الذاتية", "سير ذاتية"],
     "السير الذاتية للخبراء الرئيسيين", "السير الذاتية"),
    (["bid security", "bid bond", "bid guarantee", "tender bond", "الضمان الابتدائي", "ضمان ابتدائي", "التأمين المؤقت"],
     "ضمان العطاء / الضمان الابتدائي", "ضمان"),
    (["audited financial", "financial statements", "annual turnover", "turnover", "القوائم المالية", "الميزانيات"],
     "القوائم المالية المدققة / حجم الأعمال السنوي", "القوائم المالية"),
    (["joint venture", "association", "sub-consult", "تحالف", "ائتلاف"],
     "خطاب التحالف أو الاستشاري الفرعي (مسموح حسب الإعلان)", "التحالف"),
    (["power of attorney", "authorization letter", "تفويض", "توكيل"], "تفويض أو توكيل المفوَّض بالتوقيع", "تفويض"),
    (["iso 9001", "iso certificate", "quality management", "شهادة الجودة"], "شهادات الجودة ISO", "ISO"),
    (["registration certificate", "certificate of incorporation", "commercial registration", "السجل التجاري"],
     "السجل التجاري / شهادة التأسيس", "السجل التجاري"),
]


def notice_documents(text):
    t = norm(text)
    out = [(label, key) for keys, label, key in NOTICE_DOCS if any(norm(k) in t for k in keys)]
    if "not be evaluated at the shortlisting" in t:  # REOI: experts are not part of the shortlist stage
        out = [x for x in out if x[1] != "السير الذاتية"]
    return out


# ------------------------------------------------------------------ kinds, labels
def notice_type_ar(nt, source=""):
    n = norm(nt)
    for key, label in NOTICE_TYPES:
        if key in n:
            return label
    if source == "etimad":
        return nt or "منافسة على منصة اعتماد"
    return nt or "إعلان"


def method_ar(method, code=""):
    c = norm(code)
    m = norm(method)
    for key, label in METHODS.items():
        if c == key or f"({key})" in m or m.startswith(key) or f" {key}" in f" {m}":
            return label
    if "quality and cost" in m:
        return METHODS["qcbs"]
    if "consultant" in m and "qualification" in m:
        return METHODS["cqs"]
    if "quality based" in m or "quality-based" in m:
        return METHODS["qbs"]
    if "least cost" in m:
        return METHODS["lcs"]
    if "fixed budget" in m:
        return METHODS["fbs"]
    if "single source" in m or "direct selection" in m:
        return METHODS["sss"]
    return method


def detect_kind(t):
    src = t.get("source_key", "")
    nt = norm(t.get("notice_type", ""))
    if src in ("etimad", "etimad_prequal"):
        return "etimad"
    if src == "google_news" or nt.startswith("news"):
        return "news"
    if "general procurement notice" in nt:
        return "gpn"
    if "expression" in nt or "eoi" in nt or "اهتمام" in nt or "qualification" in nt or "تاهيل" in nt:
        return "eoi"
    if any(k in nt for k in ("proposal", "rfp", "bid", "tender", "عطاء", "مناقص", "منافس", "quotation")):
        return "rfp"
    if src in ("worldbank", "ungm"):
        return "eoi"
    return "portal"


# ------------------------------------------------------------------ ordered steps with dates
def _due(base, days, today):
    if not base:
        return None
    d = base + timedelta(days=days)
    return max(d, today)


def build_steps(kind, t, today):
    D = t.get("deadline")
    Q = t.get("inquiry_deadline")
    O = t.get("opening_date")
    sub = t.get("submission_line") or "بالطريقة المحددة في الإعلان (إيميل أو بوابة أو تسليم باليد)"
    price = t.get("booklet_price")
    contact_hint = "استخدم الإيميل الجاهز في تبويب «التواصل»."
    S = []

    def add(title, detail, due, when=""):
        S.append([title, detail, due, when])

    if kind == "eoi":
        add("اقرأ الإعلان وطابق شروط القائمة المختصرة مع خبراتكم",
            "الشروط مذكورة في تبويب «الأوراق». لو ينقصكم شرط خبرة، فكّروا في تحالف أو استشاري فرعي.", today)
        add("اطلب الشروط المرجعية (ToR) إن لم تكن مرفقة", contact_hint,
            min(today + timedelta(days=2), _due(D, -10, today)) if D else today + timedelta(days=2))
        add("قرّروا طريقة التقديم: منفردين أم بتحالف", "واطلبوا خطاب النوايا من الشريك مبكراً.", _due(D, -14, today))
        add("أرسلوا أي استفسار مكتوب", "يُفضّل قبل الموعد النهائي بـ 10 أيام على الأقل. " + contact_hint, _due(D, -10, today))
        add("جهّزوا ملف إبداء الاهتمام", "حسب قائمة «الأوراق المطلوبة».", _due(D, -5, today))
        add("مراجعة نهائية وتوقيع الخطاب", "تأكدوا من الرقم المرجعي واسم المهمة في الخطاب.", _due(D, -3, today))
        add("أرسلوا الملف قبل الموعد بيوم على الأقل", f"{sub}. احتفظوا بإثبات الإرسال (رد آلي أو إيصال).",
            _due(D, -1, today))
        add("تابعوا إعلان القائمة المختصرة", "عند اختياركم تصلكم دعوة لتقديم العرض الفني والمالي (RFP).", None,
            "بعد الموعد النهائي")
    elif kind == "gpn":
        add("اقرأ الإعلان العام وحدد المهام الاستشارية المتوقعة", "الإعلان العام يسبق طلبات إبداء الاهتمام.", today)
        add("أرسلوا خطاب تسجيل اهتمام لوحدة إدارة المشروع", "مع الملف التعريفي، واطلبوا إدراجكم في قائمة المراسلة. " + contact_hint,
            today + timedelta(days=5))
        add("تابعوا صدور طلبات إبداء الاهتمام", "الرادار ينبهكم تلقائياً عند نشرها.", None, "عند النشر")
    elif kind == "etimad":
        add("تأكدوا من جاهزية حساب المنشأة على اعتماد",
            "سجل تجاري سعودي أو ترخيص فرع أجنبي، والشهادات سارية (زكاة، تأمينات، غرفة، نطاقات).", today)
        add("اشتروا كراسة الشروط من صفحة المنافسة",
            f"قيمة الكراسة: {price}." if price else "قيمة الكراسة مذكورة في صفحة المنافسة.", today + timedelta(days=1))
        add("ادرسوا الكراسة: النطاق ومعايير التقييم والمتطلبات", "", today + timedelta(days=3))
        add("أرسلوا استفساراتكم من تبويب «الاستفسارات» في المنافسة",
            f"آخر موعد للاستفسارات: {fmt_date_ar(Q)}." if Q else "قبل آخر موعد للاستفسارات المحدد في المنافسة.",
            Q or _due(D, -10, today))
        add("استخرجوا الضمان الابتدائي (إن طُلب)", "ابدؤوا مع البنك قبل الموعد بأسبوع على الأقل.", _due(D, -7, today))
        add("جهّزوا العرض الفني", "", _due(D, -5, today))
        add("جهّزوا العرض المالي", "", _due(D, -4, today))
        add("ارفعوا العرضين على المنصة", "لا تنتظروا آخر يوم — الضغط على المنصة يزيد قرب الموعد.", _due(D, -1, today))
        add("تابعوا فتح العروض والنتيجة", "", O, "بعد الموعد النهائي")
    elif kind == "rfp":
        add("اقرأ الإعلان وتأكد من الأهلية", "", today)
        add("احصلوا على وثائق الطرح", f"قيمة الوثائق: {price}." if price else "من الجهة أو البوابة المذكورة.",
            today + timedelta(days=2))
        add("سجّلوا في الاجتماع التمهيدي أو زيارة الموقع (إن وُجدت)", "المواعيد في وثائق الطرح.", None, "حسب الوثائق")
        add("أرسلوا الاستفسارات قبل موعدها", contact_hint, Q or _due(D, -10, today))
        add("اطلبوا الضمان الابتدائي من البنك (إن طُلب)", "", _due(D, -7, today))
        add("جهّزوا العرض الفني والسير الذاتية", "", _due(D, -5, today))
        add("جهّزوا العرض المالي (منفصل)", "", _due(D, -4, today))
        add("مراجعة نهائية: التوقيعات والأختام والترقيم", "", _due(D, -2, today))
        add("قدّموا العرض قبل الموعد", f"{sub}.", _due(D, -1, today))
        add("احضروا فتح المظاريف وتابعوا التقييم", "", O, "بعد الموعد النهائي")
    elif kind == "news":
        add("ابحثوا عن الإعلان الرسمي", "استخدموا زر «ابحث عن الإعلان الرسمي» أو موقع الجهة.", today)
        add("حددوا الجهة وطريقة الحصول على الوثائق", "", today + timedelta(days=2))
        add("جهّزوا ملف التأهيل العام", "الملف التعريفي + المشاريع المماثلة + التراخيص.", today + timedelta(days=5))
        add("بعد العثور على الإعلان: اتبعوا خطواته", "الرادار سيلتقطه غالباً من المصدر الرسمي.", None, "لاحقاً")
    else:  # portal
        add("افتحوا الإعلان الرسمي واقرؤوا الشروط", "", today)
        add("تأكدوا من التسجيل في البوابة أو لدى الجهة", "بعض الدول تشترط ترخيصاً محلياً أو شريكاً محلياً.",
            today + timedelta(days=2))
        add("احصلوا على وثائق الطرح", "", today + timedelta(days=3))
        add("أرسلوا الاستفسارات حسب تعليمات الإعلان", contact_hint, _due(D, -10, today))
        add("الضمان الابتدائي (إن طُلب)", "", _due(D, -7, today))
        add("جهّزوا العرض الفني والمالي", "", _due(D, -4, today))
        add("قدّموا قبل الموعد", "", _due(D, -1, today))
        add("تابعوا النتيجة", "", None, "بعد الموعد النهائي")
    return _finish(S, D)


def _finish(S, D):
    """Keep dates in order and never later than the deadline (except steps that come after it)."""
    out, last = [], None
    for title, detail, due, when in S:
        after = when == "بعد الموعد النهائي"
        if due and D and due > D and not after:
            due = D
        if due and last and due < last and not after:
            due = last
        if due and not after:
            last = due
        out.append({"title": title, "detail": detail, "due": due.isoformat() if due else None,
                    "due_ar": fmt_date_ar(due) if due else (when or "حسب الإعلان"), "after_deadline": after})
    return out


INQUIRY_HOW = {
    "eoi": "أرسلوا الاستفسار كتابةً بالإيميل لجهة التواصل واذكروا الرقم المرجعي.",
    "gpn": "راسلوا وحدة إدارة المشروع بالإيميل.",
    "rfp": "الاستفسارات كتابةً لجهة التواصل قبل الموعد المحدد في وثائق الطرح.",
    "etimad": "الاستفسارات إلكترونياً من تبويب «الاستفسارات» داخل صفحة المنافسة على اعتماد. للمشاكل التقنية: 19990.",
    "portal": "حسب تعليمات الإعلان الرسمي — غالباً عبر البوابة أو إيميل الجهة.",
    "news": "لا توجد جهة تواصل مؤكدة بعد — ابحثوا عن الإعلان الرسمي.",
}
