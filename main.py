# main.py
from flask import Flask, send_from_directory
import threading, os, requests, feedparser, random, time
from datetime import datetime, timedelta
import time as pytime
from html import escape as html_escape

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8253247089:REPLACE_ME")  # <-- meglio da ENV su Render
CHAT_ID   = os.getenv("CHAT_ID",   "5205240046")            # tuo id/chat

# finestra pubblicazioni orarie
START_HOUR = int(os.getenv("START_HOUR", "7"))
END_HOUR   = int(os.getenv("END_HOUR", "22"))

# header per i feed (alcuni siti richiedono UA decente)
UA_HEADERS = {'User-Agent': 'TouchBot v5.1 (KitsuneLabs/Touch)'}
REQUEST_TIMEOUT = 6  # secondi: evita blocchi lunghi su Render free

# sponsor (immagine servita da Flask /static)
SHUBUKAN_IMAGE_URL = os.getenv(
    "SHUBUKAN_IMAGE_URL",
    "https://touch-worker-8ke3.onrender.com/static/shubukan_orari.png"
)

app = Flask(__name__)

# =========================
# STATO IN MEMORIA
# =========================
sent_today_hours: set[str] = set()
SENT_LINKS: set[str] = set()
ALERT_SENT_IDS: set[str] = set()
REPORT: list[dict] = []
_last_alert_check: float | None = None  # epoch seconds

# =========================
# FONTI (RSS affidabili in ITA)
# =========================
FEEDS_TECH = [
    "https://www.wired.it/feed/",
    "https://www.hwupgrade.it/news/rss/",
    "https://www.ilpost.it/tecnologia/feed/",
    "https://www.tomshw.it/feed/",
]
FEEDS_FINANCE = [
    "https://www.ilsole24ore.com/rss/finanza.xml",
    "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
]
FEEDS_GAMING = [
    "https://www.eurogamer.it/feed/rss",
    "https://multiplayer.it/rss/notizie/",
]
FEEDS_CINEMA = [
    "https://www.badtaste.it/feed/cinema/",
    "https://movieplayer.it/rss/news/",
]
FEEDS_AGENCIES = [
    "https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml",
    "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
]

# rotazione oraria
ROTATION = [FEEDS_TECH, FEEDS_FINANCE, FEEDS_GAMING, FEEDS_CINEMA, FEEDS_AGENCIES]

# parole chiave “alert”
ALERT_KEYWORDS = [
    "ultim'ora", "breaking", "allerta", "allarme", "urgente", "attentato",
    "terremoto", "guerra", "missili", "evacuazione", "blackout", "cyberattacco",
]

# =========================
# UTILITY
# =========================
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def hhmm() -> str:
    return datetime.now().strftime("%H:%M")

def escape_html_text(s: str) -> str:
    # pulizia base (summary spesso ha html e underscore)
    return html_escape(s.replace("\n", " ").strip())

def tg_send_message_html(text_html: str):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text_html, "parse_mode": "HTML", "disable_web_page_preview": False},
            timeout=REQUEST_TIMEOUT,
        )
        if not r.ok:
            log(f"⚠️ Telegram error: {r.text}")
    except Exception as e:
        log(f"⚠️ Telegram network error: {e}")

def tg_send_photo_url(photo_url: str, caption_html: str = ""):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHAT_ID, "photo": photo_url, "caption": caption_html, "parse_mode": "HTML"},
            timeout=REQUEST_TIMEOUT,
        )
        if not r.ok:
            log(f"⚠️ Telegram photo error: {r.text}")
    except Exception as e:
        log(f"⚠️ Telegram photo network error: {e}")

def sponsor_banner_html() -> str:
    ads = [
        ("<b>Shubukan Torino — Kendo &amp; Via della Presenza</b>\n"
         "Allenamenti a Torino e Carmagnola. Lezione di prova gratuita.\n"
         "<i>Allenati alla calma nel movimento. Cresci nella disciplina.</i>"),
        ("<b>Shubukan Torino — Educazione marziale gentile</b>\n"
         "Un dojo dove crescere in consapevolezza e presenza.\n"
         "<i>Non solo sport: una via di armonia.</i>"),
    ]
    return random.choice(ads)

def send_sponsor():
    caption = sponsor_banner_html()
    tg_send_photo_url(SHUBUKAN_IMAGE_URL, caption)

def fetch_feed_entries(feed_urls: list[str]) -> list:
    urls = list(feed_urls)
    random.shuffle(urls)
    all_entries = []
    for url in urls:
        try:
            resp = requests.get(url, headers=UA_HEADERS, timeout=REQUEST_TIMEOUT)
            if not resp.ok:
                log(f"⚠️ HTTP {resp.status_code} su feed {url}")
                continue
            feed = feedparser.parse(resp.content)
            if feed and getattr(feed, "entries", None):
                all_entries.extend(feed.entries)
        except Exception as ex:
            log(f"⚠️ Feed error ({url}): {ex}")
    return all_entries

def pick_fresh_entry(feed_group: list[str]):
    entries = fetch_feed_entries(feed_group)
    random.shuffle(entries)
    # prova primi 10 elementi per ridurre duplicati/rumore
    for e in entries[:10]:
        link = getattr(e, "link", "") or getattr(e, "id", "")
        if not link or link in SENT_LINKS:
            continue
        title = getattr(e, "title", "").strip()
        if not title:
            continue
        return e
    return None

def add_report(brand: str, title: str, link: str | None):
    REPORT.append({"time": hhmm(), "brand": brand, "title": title, "link": link or "-"})

def is_recent(entry, minutes=60) -> bool:
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime.fromtimestamp(pytime.mktime(entry.published_parsed))
            return datetime.now() - published <= timedelta(minutes=minutes)
    except Exception:
        pass
    return True  # quando non c'è data, non bloccare

def matches_alert(entry) -> bool:
    txt = (getattr(entry, "title", "") + " " + getattr(entry, "summary", "")).lower()
    return any(k in txt for k in ALERT_KEYWORDS)

def brand_name_for_group(group: list[str]) -> str:
    if group is FEEDS_TECH:     return "🌅 Touch Tech — Morning Spark"
    if group is FEEDS_FINANCE:  return "🍱 Touch Finance — Lunch Byte"
    if group is FEEDS_GAMING:   return "⚡ Touch Gaming — Brain Snack"
    if group is FEEDS_CINEMA:   return "🌙 Touch Cinema — Insight"
    if group is FEEDS_AGENCIES: return "📰 Touch Top News — Agenzie"
    return "📰 Touch News"

def hourly_brand_for(hour_idx: int) -> tuple[str, list[str]]:
    group = ROTATION[hour_idx % len(ROTATION)]
    return brand_name_for_group(group), group

# =========================
# CORE INVIO ARTICOLO
# =========================
def send_article(feed_group: list[str], brand_name: str) -> bool:
    entry = pick_fresh_entry(feed_group)
    if not entry:
        tg_send_message_html(f"⚠️ Nessuna notizia trovata per <b>{html_escape(brand_name)}</b>.")
        return False

    title = getattr(entry, "title", "Aggiornamento").strip()
    summary_raw = getattr(entry, "summary", "").strip()
    link = getattr(entry, "link", "") or getattr(entry, "id", "")

    # pulizia e trunc
    title_html = html_escape(title)
    summary_html = escape_html_text(summary_raw)[:500]

    msg = (f"<b>{html_escape(brand_name)}</b>\n\n"
           f"🧠 <b>{title_html}</b>\n{summary_html}\n"
           f"🔗 <a href=\"{html_escape(link)}\">Apri l'articolo</a>")

    tg_send_message_html(msg)

    # manda sponsor (foto + caption)
    send_sponsor()

    SENT_LINKS.add(link)
    add_report(brand_name, title, link)
    log(f"✅ Inviato: {brand_name} — {title}")
    return True

# =========================
# ALERTS
# =========================
def send_alerts() -> bool:
    entries = fetch_feed_entries(FEEDS_AGENCIES)
    sent_any = False
    for e in entries[:20]:
        try:
            link = getattr(e, "link", "") or getattr(e, "id", "")
            if not link or link in ALERT_SENT_IDS:
                continue
            if not is_recent(e, 60):
                continue
            if not matches_alert(e):
                continue

            title = getattr(e, "title", "Aggiornamento").strip()
            summary = getattr(e, "summary", "").strip()

            title_html = html_escape(title)
            summary_html = escape_html_text(summary)[:500]

            msg = (f"🚨 <b>ALLERTA IMPORTANTE</b> — fonte agenzia\n\n"
                   f"🗞️ <b>{title_html}</b>\n{summary_html}\n"
                   f"🔗 <a href=\"{html_escape(link)}\">Apri l'articolo</a>")
            tg_send_message_html(msg)
            ALERT_SENT_IDS.add(link)
            add_report("ALERT", title, link)
            log(f"🚨 ALERT: {title}")
            sent_any = True
        except Exception as ex:
            log(f"⚠️ Errore invio alert: {ex}")
    return sent_any

# =========================
# SCHEDULER
# =========================
def reset_daily():
    sent_today_hours.clear()
    REPORT.clear()
    log("🔄 Reset giornaliero completato.")

def scheduler_tick():
    global _last_alert_check
    now = datetime.now()
    h, m = now.hour, now.minute
    key = f"{h:02d}:00"

    # reset a mezzanotte
    if now.strftime("%H:%M") == "00:00":
        reset_daily()

    # alerts ogni ~5 minuti
    now_epoch = pytime.time()
    if _last_alert_check is None or (now_epoch - _last_alert_check) >= 300:
        _last_alert_check = now_epoch
        threading.Thread(target=send_alerts, daemon=True).start()

    # pubblicazione all'ora, tra START_HOUR e END_HOUR
    if START_HOUR <= h <= END_HOUR and m == 0 and key not in sent_today_hours:
        hour_idx = (h - START_HOUR)
        brand_name, feeds = hourly_brand_for(hour_idx)
        tg_send_message_html(f"🕐 Pubblicazione oraria: <b>{html_escape(brand_name)}</b>")
        threading.Thread(target=send_article, args=(feeds, brand_name), daemon=True).start()
        sent_today_hours.add(key)

def background_loop():
    log("🚀 Avvio TouchBot v5.1 — Smart Feeds + Alerts + Sponsor (async)")
    while True:
        try:
            scheduler_tick()
        except Exception as e:
            log(f"⚠️ Scheduler error: {e}")
        time.sleep(30)

# =========================
# ASYNC HELPER PER LE ROTTE
# =========================
def async_task(fn, *args, **kwargs):
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t

def do_send_category(slot: str):
    mapping = {
        "tech": FEEDS_TECH,
        "finance": FEEDS_FINANCE,
        "gaming": FEEDS_GAMING,
        "cinema": FEEDS_CINEMA,
        "agenzie": FEEDS_AGENCIES
    }
    feeds = mapping.get(slot)
    name = {
        "tech": "🌅 Touch Tech — Morning Spark",
        "finance": "🍱 Touch Finance — Lunch Byte",
        "gaming": "⚡ Touch Gaming — Brain Snack",
        "cinema": "🌙 Touch Cinema — Insight",
        "agenzie": "📰 Touch Top News — Agenzie",
    }.get(slot, "📰 Touch News")

    if not feeds:
        log(f"❌ Slot non valido richiesto: {slot}")
        tg_send_message_html(f"❌ Slot non valido: <b>{html_escape(slot)}</b>")
        return
    tg_send_message_html(f"⚡ Forzato: <b>{html_escape(name)}</b>")
    ok = send_article(feeds, name)
    if not ok:
        tg_send_message_html(f"⚠️ Nessuna notizia trovata per <b>{html_escape(name)}</b>.")

# =========================
# FLASK ROUTES
# =========================
@app.route("/")
def home():
    return "TouchBot v5.1 — Smart Feeds + Alerts + Sponsor (async) ✅"

@app.route("/health")
def health():
    return "ok", 200

@app.route("/ping_telegram")
def ping_telegram():
    tg_send_message_html("👋 Touch è vivo e operativo.")
    return "ping ok", 200

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

@app.route("/forza/<slot>")
def forza(slot: str):
    slot = slot.lower().strip()
    if slot in ["alert", "alerts"]:
        async_task(send_alerts)
        return "🚨 Alert: avviato controllo e invio in background."
    valid = {"tech", "finance", "gaming", "cinema", "agenzie"}
    if slot not in valid:
        return "❌ Slot non valido. Usa: tech, finance, gaming, cinema, agenzie, alert"
    async_task(do_send_category, slot)
    return f"✅ Forzatura '{slot}' ricevuta. Invio in background."

@app.route("/report")
def report_preview():
    if not REPORT:
        return "📭 Nessuna attività oggi."
    lines = [f"📊 Report — {datetime.now().strftime('%d %B %Y')}\n"]
    for r in REPORT:
        lines.append(f"• {r['time']} — {r['brand']} — {r['title']} — {r['link']}")
    return "\n".join(lines)

@app.route("/ads")
def ads_preview():
    return f"{sponsor_banner_html()}\n\nImmagine: {SHUBUKAN_IMAGE_URL}"

# =========================
# AVVIO
# =========================
if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
