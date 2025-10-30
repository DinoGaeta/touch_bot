# === TOUCHBOT v5.5 — Stable Production Build ===
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Iterable, Sequence
import os, random, threading, time, html, time as pytime

import requests
import feedparser
from flask import Flask, send_from_directory

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

START_HOUR = int(os.getenv("START_HOUR", "7"))
END_HOUR = int(os.getenv("END_HOUR", "22"))

# immagine sponsor: deve essere un .png/.jpg diretto
SHUBUKAN_IMAGE_URL = os.getenv(
    "SHUBUKAN_IMAGE_URL",
    "https://raw.githubusercontent.com/openai-examples/assets/main/shubukan_orari.png"
)

UA_HEADERS = {"User-Agent": "TouchBot v5.5 (KitsuneLabs/Touch)"}

app = Flask(__name__)

# ================== STATE ==================
sent_today_hours: set[str] = set()
SENT_LINKS: set[str] = set()
ALERT_SENT_IDS: set[str] = set()
REPORT: list[dict[str, str]] = []

# ================== SPONSOR ==================
ADS: Sequence[str] = [
    "🥋 Shubukan Torino — Kendo Jodo & Naginata\nAllenamenti a Torino e Carmagnola. Lezione di prova gratuita.\nAllenati alla calma nel movimento.",
    "🌿 Shubukan Torino — La via della spada\nUn dojo dove crescere in consapevolezza e entusiasmo.\nNon solo sport: una via di armonia.",
]

def sponsor_caption_html() -> str:
    # HTML perché Telegram col link è più stabile
    return (
        "<b>Shubukan Torino — Kendo &amp; Via della Presenza</b>\n"
        "Allenamenti a Torino e Carmagnola. Lezione di prova gratuita.\n"
        "<i>Allenati alla calma nel movimento.</i>\n"
        '👉 <a href="https://www.shubukan.it">Visita il sito</a>'
    )

def send_sponsor_photo() -> None:
    """Invia la foto sponsor. Se fallisce, logga ma non blocca l'articolo."""
    if not BOT_TOKEN or not CHAT_ID:
        log("⚠️ BOT_TOKEN o CHAT_ID non settati, salto sponsor.")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": CHAT_ID,
                "photo": SHUBUKAN_IMAGE_URL,
                "caption": sponsor_caption_html(),
                "parse_mode": "HTML",
            },
            timeout=15,
        )
        if not r.ok:
            log(f"⚠️ Telegram photo error: {r.text}")
    except Exception as e:
        log(f"⚠️ Errore rete foto sponsor: {e}")

# ================== FEEDS ==================
FEEDS_TECH = [
    "https://www.ilpost.it/tecnologia/feed/",
    "https://www.tomshw.it/feed/",
    "https://www.dday.it/feed",
    "https://www.hdblog.it/rss.xml",   # a volte 404, ma lo teniamo
]

FEEDS_FINANCE = [
    "https://www.ilsole24ore.com/rss/finanza.xml",
    "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
    "https://it.investing.com/rss/news_285.rss",
]

FEEDS_GAMING = [
    "https://www.eurogamer.it/feed/rss",
    "https://www.spaziogames.it/feed",
]

# cinema “safe” per Render
FEEDS_CINEMA = [
    "https://www.badtaste.it/feed/cinema/",
    "https://www.cinematographe.it/feed/",
]

FEEDS_AGENCIES = [
    "https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml",
    "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
]

ROTATION = [FEEDS_TECH, FEEDS_FINANCE, FEEDS_GAMING, FEEDS_CINEMA, FEEDS_AGENCIES]

ALERT_KEYWORDS = [
    "ultim'ora", "breaking", "allerta", "allarme", "urgente",
    "attentato", "terremoto", "guerra", "missili",
    "evacuazione", "blackout", "cyberattacco",
]

# ================== UTILS ==================
def log(msg: str) -> None:
    # evita l’errore “surrogates not allowed”
    safe = msg.encode("utf-8", "ignore").decode("utf-8")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}")

def hhmm() -> str:
    return datetime.now().strftime("%H:%M")

def is_recent(entry, minutes: int = 60) -> bool:
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime.fromtimestamp(pytime.mktime(entry.published_parsed))
            return datetime.now() - published <= timedelta(minutes=minutes)
    except Exception:
        pass
    return True

def matches_alert(entry) -> bool:
    txt = (getattr(entry, "title", "") + " " + getattr(entry, "summary", "")).lower()
    return any(k in txt for k in ALERT_KEYWORDS)

def clean_markdown(text: str) -> str:
    # togliamo i caratteri che spaccano Telegram quando arrivano dai feed
    text = html.escape(text)
    text = text.replace("`", "").replace("_", "").replace("*", "")
    return text

def telegram_send(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        log("⚠️ BOT_TOKEN o CHAT_ID non settati, skip telegram_send.")
        return
    safe_text = clean_markdown(text)
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": safe_text, "parse_mode": "Markdown"},
            timeout=10,
        )
        if not r.ok:
            log(f"⚠️ Telegram error: {r.text}")
    except Exception as e:
        log(f"⚠️ Telegram network error: {e}")

def fetch_feed_entries(feed_urls: Iterable[str]):
    urls = list(feed_urls)
    random.shuffle(urls)
    all_entries = []
    for url in urls:
        try:
            resp = requests.get(url, headers=UA_HEADERS, timeout=15)
            if not resp.ok:
                log(f"⚠️ HTTP {resp.status_code} su feed {url}")
                continue
            feed = feedparser.parse(resp.content)
            all_entries.extend(feed.entries)
        except Exception as ex:
            log(f"⚠️ Feed error ({url}): {ex}")
    return all_entries

def pick_fresh_entry(feed_group: Sequence[str]):
    entries = fetch_feed_entries(feed_group)
    random.shuffle(entries)
    for e in entries[:8]:
        link = getattr(e, "link", "")
        if link and link in SENT_LINKS:
            continue
        title = getattr(e, "title", "").strip()
        if not title:
            continue
        return e
    return None

def add_report(brand: str, title: str, link: str) -> None:
    REPORT.append({"time": hhmm(), "brand": brand, "title": title, "link": link or "-"})

def generate_comment(title: str, summary: str) -> str:
    hints = [
        "Sembra una notizia destinata a far discutere.",
        "Un segnale interessante per chi segue il settore.",
        "Mostra come il mercato si stia muovendo più velocemente del previsto.",
        "Un punto di svolta? Potrebbe esserlo.",
        "Vale la pena tenerla d’occhio nei prossimi giorni.",
    ]
    return random.choice(hints)

def send_article(feed_group: Sequence[str], brand_name: str) -> bool:
    entry = pick_fresh_entry(feed_group)
    if not entry:
        telegram_send(f"⚠️ Nessuna notizia trovata per *{brand_name}*.")
        return False

    title = getattr(entry, "title", "Aggiornamento")
    summary = getattr(entry, "summary", "").strip()[:400]
    link = getattr(entry, "link", "")
    comment = f"\n💬 *Commento AI:* {generate_comment(title, summary)}"

    msg = f"*{brand_name}*\n\n🧠 *{title}*\n{summary}\n🔗 {link}{comment}"
    telegram_send(msg)
    # sponsor subito dopo la notizia
    send_sponsor_photo()

    if link:
        SENT_LINKS.add(link)
    add_report(brand_name, title, link)
    log(f"[OK] Inviato: {brand_name} - {title}")
    return True

def send_alerts() -> bool:
    entries = fetch_feed_entries(FEEDS_AGENCIES)
    sent_any = False
    for e in entries[:15]:
        try:
            link = getattr(e, "link", "") or getattr(e, "id", "")
            if not link or link in ALERT_SENT_IDS:
                continue
            if not is_recent(e, 60):
                continue
            if not matches_alert(e):
                continue

            title = getattr(e, "title", "Aggiornamento").strip()
            summary = getattr(e, "summary", "").strip()[:400]
            msg = (
                "🚨 *ALLERTA IMPORTANTE* — fonte agenzia\n\n"
                f"🗞️ *{title}*\n{summary}\n🔗 {link}"
            )
            telegram_send(msg)
            ALERT_SENT_IDS.add(link)
            add_report("ALERT", title, link)
            log(f"🚨 ALERT: {title}")
            sent_any = True
        except Exception as ex:
            log(f"⚠️ Errore invio alert: {ex}")
    return sent_any

def reset_daily() -> None:
    sent_today_hours.clear()
    REPORT.clear()
    SENT_LINKS.clear()
    ALERT_SENT_IDS.clear()
    log("🔄 Reset giornaliero completato.")

def hourly_brand_for(hour_idx: int) -> tuple[str, Sequence[str]]:
    group = ROTATION[hour_idx % len(ROTATION)]
    if group is FEEDS_TECH:
        return ("🌅 Touch Tech — Morning Spark", FEEDS_TECH)
    if group is FEEDS_FINANCE:
        return ("🍱 Touch Finance — Lunch Byte", FEEDS_FINANCE)
    if group is FEEDS_GAMING:
        return ("⚡ Touch Gaming — Brain Snack", FEEDS_GAMING)
    if group is FEEDS_CINEMA:
        return ("🌙 Touch Cinema — Insight", FEEDS_CINEMA)
    return ("📰 Touch Top News — Agenzie", FEEDS_AGENCIES)

# ================== SCHEDULER ==================
def check_scheduler() -> None:
    now = datetime.now()
    h, m = now.hour, now.minute
    key = f"{h:02d}:00"

    # reset a mezzanotte
    if now.strftime("%H:%M") == "00:00":
        reset_daily()

    # allerte ogni 5 minuti
    if m % 5 == 0:
        log("🔎 Check allerte…")
        send_alerts()

    # pubblicazione oraria
    if START_HOUR <= h <= END_HOUR and m == 0 and key not in sent_today_hours:
        hour_idx = h - START_HOUR
        brand_name, feeds = hourly_brand_for(hour_idx)
        telegram_send(f"🕐 Pubblicazione oraria: *{brand_name}*")
        send_article(feeds, brand_name)
        sent_today_hours.add(key)

def background_loop() -> None:
    log("🚀 Avvio TouchBot v5.5 — Smart Feeds + Alerts + Sponsor")
    while True:
        try:
            check_scheduler()
        except Exception as e:
            log(f"⚠️ Scheduler error: {e}")
        time.sleep(60)

# ================== ROUTES ==================
@app.route("/")
def home() -> str:
    return "TouchBot v5.5 — Smart Feeds + Alerts + Sponsor ✅"

@app.route("/static/<path:filename>")
def serve_static(filename: str):
    return send_from_directory("static", filename)

@app.route("/forza/<slot>")
def forza(slot: str) -> str:
    slot = slot.lower().strip()

    if slot in ("alert", "alerts"):
        sent = send_alerts()
        return "🚨 Alert inviati." if sent else "✅ Nessuna allerta ora."

    mapping = {
        "tech": ("🌅 Touch Tech — Morning Spark", FEEDS_TECH),
        "finance": ("🍱 Touch Finance — Lunch Byte", FEEDS_FINANCE),
        "gaming": ("⚡ Touch Gaming — Brain Snack", FEEDS_GAMING),
        "cinema": ("🌙 Touch Cinema — Insight", FEEDS_CINEMA),
        "agenzie": ("📰 Touch Top News — Agenzie", FEEDS_AGENCIES),
    }

    if slot not in mapping:
        return "❌ Slot non valido. Usa: tech, finance, gaming, cinema, agenzie, alert"

    brand_name, feeds = mapping[slot]
    telegram_send(f"⚡ Forzato: *{brand_name}*")
    ok = send_article(feeds, brand_name)
    return "✅ Inviato." if ok else "⚠️ Nessuna notizia trovata."

@app.route("/forza/ads")
def forza_ads() -> str:
    send_sponsor_photo()
    return "✅ Sponsor inviato."

@app.route("/ping_telegram")
def ping_telegram() -> str:
    telegram_send("👋 TouchBot attivo e funzionante.")
    return "ok"

@app.route("/kick")
def kick() -> str:
    threading.Thread(target=background_loop, daemon=True).start()
    telegram_send("🔁 Scheduler riavviato manualmente.")
    return "✅ Scheduler riavviato."

@app.route("/health")
def health() -> str:
    return "ok"

# ================== AUTO START (per Gunicorn) ==================
def start_scheduler():
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    log("🧭 Scheduler avviato (compatibile Gunicorn).")

start_scheduler()

if __name__ == "__main__":
    # locale / debug
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

