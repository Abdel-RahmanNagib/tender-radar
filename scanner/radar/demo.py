"""Sample (fictional) data – used by the tests and by `run.py --demo` to try the app without internet.
Every entity, e-mail and phone number below is an example, not a real tender."""
from datetime import timedelta
from urllib.parse import unquote_plus


def _d(today, n):
    return (today + timedelta(days=n)).isoformat()


def fetchers(today):
    WB_TEXT = """<p>ARAB REPUBLIC OF EGYPT</p><p>REQUEST FOR EXPRESSIONS OF INTEREST (CONSULTING SERVICES – FIRMS SELECTION)</p>
<p>Assignment Title: Detailed Design and Construction Supervision of Stormwater Drainage and Flood Protection Works in Upper Egypt Governorates (Example).</p>
<p>The consulting services include hydrological studies, hydraulic modelling of wadis, detailed design of drainage networks and culverts, and supervision of works.</p>
<p>The Project Management Unit now invites eligible consulting firms to indicate their interest in providing the Services. Interested Consultants should provide information demonstrating that they have the required qualifications and relevant experience to perform the Services.</p>
<p>The shortlisting criteria are: (a) core business and years in business of at least 10 years; (b) relevant experience in at least 3 similar assignments of stormwater drainage design in the last 10 years; (c) technical and managerial capability of the firm.</p>
<p>Key Experts will not be evaluated at the shortlisting stage.</p>
<p>Consultants may associate with other firms in the form of a joint venture or a sub-consultancy to enhance their qualifications.</p>
<p>Further information can be obtained at the address below during office hours 09:00 to 15:00 hours.</p>
<p>Expressions of interest must be delivered in a written form to the address below by e-mail by the deadline.</p>
<p>Attn: Eng. Mona Example, Procurement Specialist. E-mail: pmu.procurement@example.org, Tel: +20 2 0000 1234, Mobile: +20 100 000 1234</p>"""

    def wb(url, **kw):
        if "qterm=Egypt" in url:
            return {"procnotices": [
                {"id": "OP00999001", "notice_type": "Request for Expression of Interest", "noticedate": "20-Nov-2026",
                 "submission_deadline_date": _d(today, 46) + "T00:00:00Z", "submission_deadline_time": "14:00",
                 "project_ctry_name": "Egypt, Arab Republic of", "project_id": "P000001",
                 "project_name": "Climate Resilient Infrastructure Project (Example)",
                 "bid_reference_no": "EG-PMU-000001-CS-QCBS",
                 "bid_description": "Detailed Design and Supervision of Stormwater Drainage and Flood Protection Works",
                 "procurement_group": "CS", "procurement_method_code": "QCBS",
                 "procurement_method_name": "Quality And Cost-Based Selection",
                 "contact_name": "Eng. Mona Example", "contact_email": "pmu.procurement@example.org",
                 "contact_phone_no": "+20 2 0000 1234", "contact_organization": "Project Management Unit (Example)",
                 "contact_address": "Example Street, Cairo, Egypt", "notice_text": WB_TEXT},
                {"id": "OP00999003", "notice_type": "Contract Award", "noticedate": "10-Nov-2026",
                 "project_ctry_name": "Egypt, Arab Republic of", "bid_description": "Design of sewerage network",
                 "procurement_group": "CS"},
                {"id": "OP00999004", "notice_type": "Request for Expression of Interest", "noticedate": "01-Sep-2026",
                 "submission_deadline_date": _d(today, -30) + "T00:00:00Z", "project_ctry_name": "Egypt, Arab Republic of",
                 "bid_description": "Consultancy for road safety design review", "procurement_group": "CS"},
                {"id": "OP00999005", "notice_type": "Request for Expression of Interest", "noticedate": "18-Nov-2026",
                 "submission_deadline_date": _d(today, 20) + "T00:00:00Z", "project_ctry_name": "Egypt, Arab Republic of",
                 "bid_description": "Individual Consultant – Hydrologist", "procurement_group": "CS",
                 "procurement_method_code": "INDV", "procurement_method_name": "Individual Consultant Selection"},
            ]}
        if "qterm=Jordan" in url:
            return {"procnotices": [
                {"id": "OP00999010", "notice_type": "General Procurement Notice", "noticedate": "15-Nov-2026",
                 "project_ctry_name": "Jordan", "project_id": "P000010",
                 "project_name": "Water Sector Efficiency Program (Example)",
                 "bid_description": "Water Sector Efficiency Program – consulting services for design of water networks and wastewater pumping stations",
                 "procurement_group": "CS", "contact_name": "Project Coordinator (Example)",
                 "contact_email": "wsep@example.org", "contact_phone_no": "962600000000",
                 "contact_organization": "Ministry PMU (Example)",
                 "notice_text": "<p>Consulting services will include feasibility studies, detailed design of water distribution networks and supervision. Interested consulting firms may express interest by email.</p>"}]}
        if "qterm=Iraq" in url:
            return {"procnotices": [
                {"id": "OP00999002", "notice_type": "Invitation for Bids", "noticedate": "18-Nov-2026",
                 "submission_deadline_date": _d(today, 25) + "T00:00:00Z", "project_ctry_name": "Iraq",
                 "bid_description": "Supply of vehicles and laptops for the PMU", "procurement_group": "GO"}]}
        return {"procnotices": []}

    def etimad(url, **kw):
        if "AllPreQualificationsAsync" in url:
            if "TenderName=%D8%A7%D8%B3%D8%AA%D8%B4%D8%A7%D8%B1%D9%8A" not in url:  # only 'استشاري'
                return {"data": []}
            return {"data": [{"preQualificationIdString": "pq-777==",
                              "preQualificationName": "تأهيل مسبق لمكاتب استشارية لتصميم شبكات المياه والصرف الصحي (مثال)",
                              "agencyName": "شركة مياه (مثال)", "referenceNumber": "PQ-2026-0077",
                              "lastApplicationDate": _d(today, 18), "qualificationTypeName": "تأهيل مسبق"}]}
        if "PageNumber=1" not in url or "MultipleSearch=" not in url:
            return {"data": []}
        kw_ = unquote_plus(url.split("MultipleSearch=")[1])
        if kw_ != "تصميم":
            return {"data": []}
        return {"data": [
            {"tenderIdString": "abc123==",
             "tenderName": "تصميم وإشراف على مشروع تصريف مياه الأمطار ودرء أخطار السيول بحي النرجس (مثال)",
             "agencyName": "أمانة منطقة (مثال)", "branchName": "وكالة المشاريع", "tenderTypeName": "منافسة عامة",
             "referenceNumber": "261139010555", "submitionDate": _d(today, -3) + "T10:00:00",
             "lastOfferPresentationDate": _d(today, 33) + "T10:00:00", "lastEnqueriesDate": _d(today, 15),
             "offersOpeningDate": _d(today, 34) + "T10:00:00",
             "condetionalBookletPrice": 1500, "tenderActivityName": "الخدمات الاستشارية الهندسية"},
            {"tenderIdString": "def456==", "tenderName": "تنفيذ مشروع سفلتة وإنارة طرق بالمخطط الصناعي (مثال)",
             "agencyName": "بلدية (مثال)", "tenderTypeName": "منافسة عامة", "referenceNumber": "261139010600",
             "lastOfferPresentationDate": _d(today, 20) + "T10:00:00", "tenderActivityName": "المقاولات"},
            {"tenderIdString": "zzz999==", "tenderName": "توريد أجهزة حاسب آلي وطابعات", "agencyName": "جامعة (مثال)",
             "tenderTypeName": "منافسة عامة", "referenceNumber": "261139010777",
             "lastOfferPresentationDate": _d(today, 12) + "T10:00:00", "tenderActivityName": "تقنية المعلومات"},
        ]}

    def ungm(url, data=None, **kw):
        if (data or {}).get("Title") != "drainage":
            return ""
        return f"""<div class="tableRow dataRow notice-table" data-noticeid="275001">
 <div class="tableCell resultTitle"><span>Consultancy services for design of stormwater drainage and road rehabilitation in Gaza (Example)</span></div>
 <div class="tableCell">{_d(today, 20)}</div><div class="tableCell">{_d(today, -6)}</div>
 <div class="tableCell">UNOPS</div><div class="tableCell">Request for proposal</div>
 <div class="tableCell">RFP/2026/00001</div><div class="tableCell">State of Palestine</div></div>"""

    def monaqasat(url, **kw):
        if not url.endswith("/1"):
            return "<table></table>"
        rows = [
            ("1", "5301", "Public Tender", "2026",
             "Consultancy services for design and supervision of surface water drainage network – Al Wakra (Example), for further details please contact by email address: procurement@example.qa",
             "Published", "Public Works Authority (Example)", "3,000.00 QAR", "50,000.00 QAR"),
            ("2", "5299", "Public Tender", "2026", "Supply of school furniture", "Published",
             "Ministry (Example)", "500.00 QAR", "10,000.00 QAR"),
            ("3", "5290", "Public Tender", "2026", "Design of roads and utilities for industrial area (Example)",
             "Awarded", "Ministry (Example)", "1,000.00 QAR", "20,000.00 QAR"),
        ]
        body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
        return f"<table><tr><th>S</th><th>Tender number</th></tr>{body}</table>"

    def news(url, **kw):
        if "hl=ar" not in url or "%D8%B5%D8%B1%D9%81" not in url:  # one Arabic query only
            return "<rss><channel></channel></rss>"
        pub = (today - timedelta(days=2)).strftime("%a, %d %b %Y 08:00:00 GMT")
        return f"""<rss><channel><item><title>طرح مناقصة استشارية لتصميم شبكات الصرف الصحي والطرق بالمنطقة الصناعية في صحار – سلطنة عمان (مثال)</title>
<link>https://news.example.com/oman-tender-123</link><pubDate>{pub}</pubDate>
<description>دعت الجهة المكاتب الاستشارية المؤهلة لتقديم عروضها الفنية والمالية لتصميم شبكات الصرف الصحي والطرق</description><source url="x">صحيفة (مثال)</source></item></channel></rss>"""

    def web(url, **kw):
        if "portal.example.ae" in url:
            return ('<a href="/tenders/ex-88">Consultancy Services for Hydrology and Flood Risk Study and Stormwater '
                    'Master Plan – Ras Al Khaimah (Example)</a><a href="/about">About the portal</a>'
                    '<a href="/t/2">Supply of office furniture for ministry building</a>')
        return ""

    def detail(url, **kw):
        if "ungm.org" in url:
            return ("<h2>Contact information</h2><p>Name: Procurement Unit (Example)</p>"
                    "<p>Email: procurement.gaza@example.org</p><p>Telephone: +970 8 000 0000</p>"
                    "<p>Proposals must be submitted electronically through the UNOPS eSourcing system.</p>")
        if "etimad" in url:
            return ("<div>الغرض من المنافسة</div><div>تصميم شبكة تصريف وإشراف على التنفيذ (مثال)</div>"
                    "<div>مدة العقد</div><div>18 شهر</div><div>طريقة تقديم العروض</div><div>ملفين منفصلين (فني ومالي)</div>"
                    "<div>مطلوب ضمان الإبتدائي</div><div>نعم</div>")
        if "portal.example.ae" in url:
            return "<p>Closing date: " + (today + timedelta(days=12)).strftime("%d/%m/%Y") + \
                   "</p><p>For clarifications contact tenders@example.ae, Tel: +971 2 000 0000</p>"
        return ""

    return {"worldbank": wb, "etimad": etimad, "ungm": ungm, "monaqasat": monaqasat, "google_news": news,
            "rss_feeds": lambda url, **kw: "", "web_pages": web, "detail": detail}


def demo_profile_overrides(profile):
    """Point the generic portal list at one fake page so the demo stays offline."""
    p = dict(profile)
    p["sources"] = dict(profile["sources"])
    p["sources"]["web_pages"] = {"pages": [{"name": "بوابة مشتريات حكومية (مثال)", "country": "UAE",
                                            "url": "https://portal.example.ae/"}]}
    return p


def mark_demo(data_dir):
    """Flag the sample data so the app shows a 'demo' banner, point links to example.com and vary dates."""
    import json
    import os
    from datetime import datetime, timedelta, timezone
    path = os.path.join(data_dir, "tenders.json")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    doc["demo"] = True
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for i, r in enumerate(doc["tenders"]):
        for link in r.get("links", []):
            if "google.com/search" not in link["url"]:
                link["url"] = f"https://example.com/notice/{r['id']}"
        r["first_seen"] = (now - timedelta(days=(0 if i < 3 else 2 + i))).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
