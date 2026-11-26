"""Notifications: ntfy (phone/PC app), Telegram, e-mail, console."""
import html
import json
import smtplib
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .common import fmt_date_ar, http, parse_date


def days_ar(n):
    """Arabic counting: 1 يوم واحد، 2 يومان، 3-10 أيام، 11+ يوماً"""
    if n == 0:
        return "ينتهي اليوم"
    if n == 1:
        return "باقي يوم واحد"
    if n == 2:
        return "باقي يومان"
    if 3 <= n <= 10:
        return f"باقي {n} أيام"
    return f"باقي {n} يوماً"


def count_ar(n):
    if n == 1:
        return "فرصة واحدة"
    if n == 2:
        return "فرصتان"
    if 3 <= n <= 10:
        return f"{n} فرص"
    return f"{n} فرصة"


def days_left(rec, today):
    d = parse_date(rec.get("deadline"))
    return (d - today).days if d else None


def deep_link(rec, app_url):
    return f"{app_url.rstrip('/')}/#t-{rec['id']}" if app_url else rec.get("links", [{}])[0].get("url", "")


def first_contact(rec):
    c = (rec.get("contacts") or [{}])[0]
    parts = []
    if c.get("emails"):
        parts.append(c["emails"][0])
    if c.get("phones"):
        parts.append(c["phones"][0]["display"])
    return " | ".join(parts)


def short_text(rec, today):
    n = days_left(rec, today)
    lines = [rec["title"][:200]]
    if rec.get("client"):
        lines.append(f"الجهة: {rec['client'][:120]}")
    lines.append(f"النوع: {rec['notice_type_ar']}")
    if rec.get("deadline"):
        lines.append(f"آخر موعد: {fmt_date_ar(rec['deadline'])}" + (f" ({days_ar(n)})" if n is not None else ""))
    else:
        lines.append("آخر موعد: غير مذكور في المصدر")
    lines.append(f"التخصص: {'، '.join(rec['match']['disciplines'][:3])} — {rec['match']['level_ar']}")
    fc = first_contact(rec)
    if fc:
        lines.append(f"للاستفسار: {fc}")
    lines.append("افتح الإشعار لعرض الأوراق المطلوبة وخطوات التقديم.")
    return "\n".join(lines)


def headline(rec, today):
    n = days_left(rec, today)
    h = f"{rec.get('flag', '')} فرصة جديدة – {rec['country_ar']}".strip()
    if n is not None:
        h += f" – {days_ar(n)}"
    return h


class Notifier:
    def __init__(self, channels, state, app_url="", log=print):
        self.ch = channels
        self.state = state
        self.app_url = app_url
        self.log = log
        self.errors = []
        self.sent = 0

    # ------------------------------------------------------------- public
    def tender(self, rec, today):
        n = days_left(rec, today)
        link = deep_link(rec, self.app_url)
        official = rec.get("links", [{}])[0].get("url", "")
        if self.ch.get("console", True):
            self.log("\n" + "=" * 60 + f"\n{headline(rec, today)}\n{short_text(rec, today)}\n{link}")
        if self.ch.get("ntfy_topic"):
            actions = [{"action": "view", "label": "الأوراق والخطوات", "url": link}]
            if official and official != link:
                actions.append({"action": "view", "label": "الإعلان الرسمي", "url": official})
            self._ntfy(headline(rec, today), short_text(rec, today), link, actions,
                       priority=4 if n is not None and n <= 10 else 3,
                       tags=["rotating_light"] if n is not None and n <= 5 else ["bell"])
        if self.ch.get("telegram_token"):
            buttons = [[{"text": "📋 الأوراق والخطوات", "url": link}]]
            if official and official != link:
                buttons[0].append({"text": "🔗 الإعلان الرسمي", "url": official})
            self._telegram(self._telegram_html(rec, today), buttons)
        if self._email_on():
            self._email(f"{headline(rec, today)} | {rec['title'][:80]}", self._email_html(rec, today, link))
        self.sent += 1

    def summary(self, title, body, click=""):
        click = click or self.app_url
        if self.ch.get("console", True):
            self.log(f"\n[{title}]\n{body}")
        if self.ch.get("ntfy_topic"):
            self._ntfy(title, body, click, [{"action": "view", "label": "فتح التطبيق", "url": click}] if click else [],
                       priority=3, tags=["bar_chart"])
        if self.ch.get("telegram_token"):
            self._telegram(f"<b>{html.escape(title)}</b>\n{html.escape(body)}",
                           [[{"text": "📱 فتح التطبيق", "url": click}]] if click else None)
        if self._email_on():
            self._email(title, "<div dir='rtl' style='font-family:Tahoma,Arial'>" +
                        html.escape(body).replace("\n", "<br>") + "</div>")

    def sync_subscribers(self):
        """Telegram: anyone who presses Start on the bot is subscribed automatically."""
        token = self.ch.get("telegram_token")
        if not token:
            return
        chats = self.state.setdefault("telegram_chats", [])
        for cid in self.ch.get("telegram_chat_ids") or []:
            if str(cid) not in [str(c) for c in chats]:
                chats.append(str(cid))
        try:
            off = self.state.get("telegram_offset", 0)
            r = json.loads(http(f"https://api.telegram.org/bot{token}/getUpdates?offset={off}&timeout=0", retries=1))
            for u in r.get("result", []):
                self.state["telegram_offset"] = u["update_id"] + 1
                msg = u.get("message") or u.get("channel_post") or {}
                cid = str((msg.get("chat") or {}).get("id", ""))
                text = (msg.get("text") or "").strip().lower()
                if not cid:
                    continue
                if text.startswith("/stop") and cid in chats:
                    chats.remove(cid)
                    self._tg_send(cid, "تم إيقاف الإشعارات. أرسل /start للعودة.")
                elif cid not in chats:
                    chats.append(cid)
                    self._tg_send(cid, "✅ تم الاشتراك في إشعارات رادار المناقصات الاستشارية.\n"
                                       "ستصلك رسالة عند ظهور أي فرصة مناسبة. لإيقافها أرسل /stop")
        except Exception as e:  # noqa: BLE001
            self.errors.append(f"telegram updates: {e}")

    # ------------------------------------------------------------- channels
    def _ntfy(self, title, message, click, actions, priority=3, tags=None):
        server = (self.ch.get("ntfy_server") or "https://ntfy.sh").rstrip("/")
        payload = {"topic": self.ch["ntfy_topic"], "title": title[:250], "message": message[:3800],
                   "priority": priority, "tags": tags or ["bell"]}
        if click:
            payload["click"] = click
        if actions:
            payload["actions"] = actions[:3]
        try:
            http(server + "/", data=payload, retries=1)
        except Exception as e:  # noqa: BLE001
            self.errors.append(f"ntfy: {e}")

    def _tg_send(self, chat_id, text, buttons=None):
        data = {"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": "true"}
        if buttons:
            data["reply_markup"] = json.dumps({"inline_keyboard": buttons}, ensure_ascii=False)
        r = json.loads(http(f"https://api.telegram.org/bot{self.ch['telegram_token']}/sendMessage",
                            data=urllib.parse.urlencode(data).encode(),
                            headers={"Content-Type": "application/x-www-form-urlencoded"}, retries=1))
        if not r.get("ok"):
            raise RuntimeError(r.get("description", r))

    def _telegram(self, text, buttons=None):
        for cid in list(self.state.get("telegram_chats", [])):
            try:
                self._tg_send(cid, text, buttons)
            except Exception as e:  # noqa: BLE001
                self.errors.append(f"telegram {cid}: {e}")

    def _email_on(self):
        em = self.ch.get("email") or {}
        return bool(em.get("smtp_host") and em.get("username") and em.get("password") and em.get("to"))

    def _email(self, subject, html_body):
        em = self.ch["email"]
        to = em["to"] if isinstance(em["to"], list) else [x.strip() for x in str(em["to"]).split(",")]
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"], msg["From"], msg["To"] = subject, em.get("from") or em["username"], ", ".join(to)
            msg.attach(MIMEText(html_body, "html", "utf-8"))
            port = int(em.get("smtp_port") or 465)
            if port == 465:
                s = smtplib.SMTP_SSL(em["smtp_host"], port, timeout=40)
            else:
                s = smtplib.SMTP(em["smtp_host"], port, timeout=40)
                s.starttls()
            with s:
                s.login(em["username"], em["password"])
                s.sendmail(msg["From"], to, msg.as_string())
        except Exception as e:  # noqa: BLE001
            self.errors.append(f"email: {e}")

    # ------------------------------------------------------------- rich formats
    @staticmethod
    def _telegram_html(rec, today):
        e = html.escape
        n = days_left(rec, today)
        L = [f"<b>🔔 {e(headline(rec, today))}</b>", f"<b>{e(rec['title'][:300])}</b>", ""]
        if rec.get("client"):
            L.append(f"🏛 الجهة: {e(rec['client'])}")
        L.append(f"📄 النوع: {e(rec['notice_type_ar'])}")
        if rec.get("reference"):
            L.append(f"🔢 الرقم المرجعي: {e(rec['reference'])}")
        L.append("⏳ آخر موعد: " + (e(fmt_date_ar(rec["deadline"])) + (f" ({days_ar(n)})" if n is not None else "")
                                   if rec.get("deadline") else "غير مذكور في المصدر"))
        L.append(f"🎯 التخصص: {e('، '.join(rec['match']['disciplines'][:3]))} — {e(rec['match']['level_ar'])}")
        c = rec["contacts"][0]
        if c.get("emails") or c.get("phones"):
            L.append("☎️ للاستفسار: " + " | ".join(e(x) for x in c.get("emails", [])[:2] +
                                                   [p["display"] for p in c.get("phones", [])[:2]]))
        L += ["", "📋 أهم الأوراق المطلوبة:"] + [f"• {e(d['title'])}" for d in rec["documents"][:5]]
        if rec.get("steps"):
            s = rec["steps"][0]
            L += ["", f"🪜 أول خطوة: {e(s['title'])} — {e(s['due_ar'])}"]
        return "\n".join(L)

    @staticmethod
    def _email_html(rec, today, link):
        e = html.escape
        n = days_left(rec, today)
        rows = [("الدولة", rec["country_ar"]), ("الجهة", rec.get("client")), ("نوع الإعلان", rec["notice_type_ar"]),
                ("الرقم المرجعي", rec.get("reference")),
                ("آخر موعد", (fmt_date_ar(rec["deadline"]) + (f" ({days_ar(n)})" if n is not None else ""))
                 if rec.get("deadline") else "غير مذكور"),
                ("طريقة الاختيار", rec.get("method_ar")), ("التمويل", rec.get("funding")),
                ("التخصص", "، ".join(rec["match"]["disciplines"]) + " — " + rec["match"]["level_ar"])]
        table = "".join(f"<tr><td style='color:#5b6b7b;padding:4px 8px'>{e(a)}</td><td style='padding:4px 8px'>{e(str(b))}</td></tr>"
                        for a, b in rows if b)
        contacts = ""
        for c in rec["contacts"]:
            items = [e(c.get("name", "")), e(c.get("org", ""))] + \
                    [f"<a href='mailto:{e(x)}'>{e(x)}</a>" for x in c.get("emails", [])] + \
                    [f"<a href='tel:{e(p['tel'])}'>{e(p['display'])}</a>" for p in c.get("phones", [])]
            items = [i for i in items if i]
            contacts += f"<p><b>{e(c['title'])}</b><br>{' · '.join(items) or e(c.get('note', ''))}</p>"
        docs = "".join(f"<li>{e(d['title'])}{' <b>(مذكور في الإعلان)</b>' if d['from_notice'] else ''}</li>"
                       for d in rec["documents"])
        steps = "".join(f"<li>{e(s['title'])} — <span style='color:#5b6b7b'>{e(s['due_ar'])}</span></li>"
                        for s in rec["steps"])
        return f"""<div dir="rtl" style="font-family:Tahoma,Arial;font-size:14px;color:#1b2733;max-width:680px">
<h2 style="color:#0b3a5b;margin:0 0 8px">{e(rec['title'])}</h2>
<table style="border-collapse:collapse;margin-bottom:10px">{table}</table>
<p><a href="{e(link)}" style="background:#0b3a5b;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none">فتح الأوراق والخطوات في التطبيق</a></p>
<h3 style="color:#0b3a5b">جهة التواصل للاستفسار</h3>{contacts}
<h3 style="color:#0b3a5b">الأوراق المطلوبة</h3><ul>{docs}</ul>
<h3 style="color:#0b3a5b">خطوات التقديم بالترتيب</h3><ol>{steps}</ol></div>"""
