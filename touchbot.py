from __future__ import annotations

import os
import time
import random
import threading
import requests
import feedparser
from datetime import datetime, timedelta
from typing import Iterable, Sequence
from flask import Flask, send_from_directory
import time as pytime

# ============== CONFIG ==============
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

START_HOUR = int(os.getenv("START_HOUR", "7"))
END_HOUR = int(os.getenv("END_HOUR", "22"))

SHUBUKAN_IMAGE_URL = os.getenv(
    "SHUBUKAN_IMAGE_URL",
    "https://touch-worker-8ke3.onrender.com/static/shubukan_orari.png",
)

UA_HEADERS = {"User-Agent": "TouchBot v5.2 (KitsuneLabs/Touch)"}

app = Flask(__name__)

# Stato in memoria
sent_today_hours: set[str] = set()
SENT_LINKS: set[str] = set()
ALERT_SENT_IDS: set[str] = set()
REPORT: list[dict[str, str]] = []

# ============== UTIL ==============
def sanitize(text: str) -> str:
    """Rimuove eventuali surrogati/char non encodabili per sicurezza."""
    if not isinstance(text, str):
        text = str(text)
    return text.encode("utf-8", "ignore").decode("utf-8", "ignore")

def log(msg: str) -> None:
    try:
        safe = sanitize(msg)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}", flush=True)
    except Exception as e:
        print(f"[LOG ERROR] {e}", flush=True)

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

def telegram_send(text: str) -> None:
    text = sanitize(text)
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        if not r.ok:
            log(f"⚠️ Telegram error: {r.text}")
    except Exception as e:
        log(f"⚠️ Telegram network error: {e}")

# ============== ADS (Sponsor) ==============
ADS: Sequence[str] = (
    "🥋 *Shubukan Torino — Kendo & Via della Presenza*\n"
    "Allenamenti a Torino e Carmagnola. Lezione di prova gratuita.\n"
    "_Allenati alla calma nel movimento. Cresci nella disciplina._",
    "🌿 *Shubukan Torino — Educazione marziale gentile*\n"
    "Un dojo dove crescere in consapevolezza e presenza.\n"
    "_Non solo sport: una via di armonia._",
)

def sponsor_banner() -> str:
    return random.choice(ADS)

def send_sponsor_photo() -> None:
    """Invia la foto sponsor via URL (richiesto da Telegram)."""
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": CHAT_ID,
                "photo": SHUBUKAN_IMAGE_URL,  # IMPORTANTE: URL diretto a immagine
                "caption": sanitize(sponsor_banner()),
                "parse_mode": "Markdown",
            },
            timeout=15,
        )
        if not r.ok:
            log(f"⚠️ Telegram photo error: {r.text}")
    except Exception as e:
        log(f"⚠️ Errore rete foto sponsor: {e}")

# ============== FEEDS ==============
FEEDS_TECH = [
    "https://www.ilpost.it/tecnologia/feed/",
    "https://www.tomshw.it/feed/",
    "https://www.dday.it/feed",
    "https://www.hdblog.it/rss.xml",
]

FEEDS_FINANCE = [
    "https://www.ilsole24ore.com/rss/finanza.xml",
    "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
    "https://it.investing.com/rss/news_285.rss",  # Investing.com Italia (RSS pubblico)
]

FEEDS_GAMING = [
    "https://www.eurogamer.it/feed/rss",
    "https://www.spaziogames.it/feed",
    "https://www.ign.com/rss",  # può dare 404 a tratti: gestiamo retry/skip
]

FEEDS_CINEMA = [
    "https://www.comingsoon.it/rss/news.xml",
    "https://www.cineblog.it/rss",
]

FEEDS_AGENCIES = [
    "https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml",
    "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
]

ROTATION = [FEEDS_TECH, FEEDS_FINANCE, FEEDS_GAMING, FEEDS_CINEMA, FEEDS_AGENCIES]

ALERT_KEYWORDS = [
    "ultim'ora",
    "breaking",
    "allerta",
    "allarme",
    "urgente",
    "attentato",
    "terremoto",
    "guerra",
    "missili",
    "evacuazione",
    "blackout",
    "cyberattacco",
]

# ============== FEED HELPERS ==============
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
    for e in entries[:10]:
        link = getattr(e, "link", "")
        if link and link in SENT_LINKS:
            continue
        title = sanitize(getattr(e, "title", "").strip())
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
        "Il mercato si muove più veloce del previsto.",
        "Potenziale punto di svolta.",
        "Da tenere d’occhio nei prossimi giorni.",
    ]
    return random.choice(hints)

def send_article(feed_group: Sequence[str], brand_name: str) -> bool:
    entry = pick_fresh_entry(feed_group)
    if not entry:
        telegram_send(f"⚠️ Nessuna notizia trovata per *{brand_name}*.")
        return False

    title = sanitize(getattr(entry, "title", "Aggiornamento"))
    summary = sanitize(getattr(entry, "summary", "").strip())[:400]
    link = sanitize(getattr(entry, "link", ""))

    comment = f"\n💬 *Commento AI:* {generate_comment(title, summary)}"
    msg = f"*{brand_name}*\n\n🧠 *{title}*\n{summary}\n🔗 {link}{comment}"

    telegram_send(msg)
    send_sponsor_photo()
    if link:
        SENT_LINKS.add(link)
    add_report(brand_name, title, link)
    log(f"[OK] Inviato: {brand_name} - {title}")
    return True

# ============== ALERTS ==============
def matches_alert(entry) -> bool:
    txt = (getattr(entry, "title", "") + " " + getattr(entry, "summary", "")).lower()
    return any(k in txt for k in ALERT_KEYWORDS)

def send_alerts() -> bool:
    entries = fetch_feed_entries(FEEDS_AGENCIES)
    sent_any = False
    for e in entries[:15]:
        try:
            link = sanitize(getattr(e, "link", "") or getattr(e, "id", ""))
            if not link or link in ALERT_SENT_IDS:
                continue
            if not is_recent(e, 60):
                continue
            if not matches_alert(e):
                continue

            title = sanitize(getattr(e, "title", "Aggiornamento").strip())
            summary = sanitize(getattr(e, "summary", "").strip())[:400]
            msg = (
                "🚨 *ALLERTA IMPORTANTE* — fonte agenzia\n\n"
                f"🗞️ *{title}*\n{summary}\n🔗 {link}"
            )
            telegram_send(msg)
            ALERT_SENT_IDS.add(link)
            add_report("ALERT", title, link)
            log(f"[ALERT] {title}")
            sent_any = True
        except Exception as ex:
            log(f"⚠️ Errore invio alert: {ex}")
    return sent_any

# ============== SCHEDULE ==============
def reset_daily() -> None:
    sent_today_hours.clear()
    REPORT.clear()
    SENT_LINKS.clear()
    ALERT_SENT_IDS.clear()
    log("[RESET] Giornaliero completato.")

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

def check_scheduler() -> None:
    now = datetime.now()
    h, m = now.hour, now.minute
    key = f"{h:02d}:00"

    # reset a mezzanotte
    if now.strftime("%H:%M") == "00:00":
        reset_daily()

    # check allerte ogni 5 minuti
    if m % 5 == 0:
        log("[SCAN] Check allerte…")
        send_alerts()

    # pubblicazione oraria
    if START_HOUR <= h <= END_HOUR and m == 0 and key not in sent_today_hours:
        hour_idx = (h - START_HOUR) % len(ROTATION)
        brand_name, feeds = hourly_brand_for(hour_idx)
        telegram_send(f"🕐 Pubblicazione oraria: *{brand_name}*")
        send_article(feeds, brand_name)
        sent_today_hours.add(key)

def send_daily_report() -> None:
    if not REPORT:
        telegram_send("📊 Nessuna attività oggi.")
        return
    lines = [f"📊 *TouchBot Report — {datetime.now().strftime('%d %B %Y')}*\n"]
    for r in REPORT:
        lines.append(f"✅ {r['brand']} ({r['time']})\n• {r['title']}\n• {r['link']}\n")
    telegram_send("\n".join(lines))

def background_loop() -> None:
    log("🚀 Avvio TouchBot v5.2 — Smart Feeds + Alerts + Sponsor")
    while True:
        try:
            check_scheduler()
        except Exception as e:
            log(f"⚠️ Scheduler error: {e}")
        time.sleep(60)

# ============== ROUTES ==============
@app.route("/")
def home() -> str:
    return "TouchBot v5.2 — Smart Feeds + Alerts + Sponsor ✅"

@app.route("/static/<path:filename>")
def serve_static(filename: str):
    return send_from_directory("static", filename)

@app.route("/forza/<slot>")
def forza(slot: str) -> str:
    slot = slot.lower().strip()

    if slot in ["alert", "alerts"]:
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

@app.route("/report")
def report_preview() -> str:
    if not REPORT:
        return "📡 Nessuna attività oggi."
    lines = [f"📊 Anteprima Report — {datetime.now().strftime('%d %B %Y')}\n"]
    for r in REPORT:
        lines.append(f"• {r['time']} — {r['brand']} — {r['title']}")
    return "\n".join(lines)

@app.route("/ads")
def ads_preview() -> str:
    return f"{sponsor_banner()}\n\nImmagine: {SHUBUKAN_IMAGE_URL}"

@app.route("/ping_telegram")
def ping_telegram() -> str:
    telegram_send("👋 Touch è vivo e operativo.")
    return "ok"

@app.route("/health")
def health() -> str:
    return "ok"

# ============== BOOT ==============
if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
