from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Sequence

import feedparser
import os
import random
import requests
import threading
import time
from flask import Flask, send_from_directory

import time as pytime

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

START_HOUR = int(os.getenv("START_HOUR", "7"))
END_HOUR = int(os.getenv("END_HOUR", "22"))
SHUBUKAN_IMAGE_URL = os.getenv(
    "SHUBUKAN_IMAGE_URL", "https://touch-worker-8ke3.onrender.com/static/shubukan_orari.png"
)

UA_HEADERS = {"User-Agent": "TouchBot v5.1 (KitsuneLabs/Touch)"}

app = Flask(__name__)

sent_today_hours: set[str] = set()
SENT_LINKS: set[str] = set()
ALERT_SENT_IDS: set[str] = set()
REPORT: list[dict[str, str]] = []

# === SPONSOR: Shubukan Torino ===
ADS: Sequence[str] = (
    "\ud83c\udfcb\ufe0f *Shubukan Torino \u2014 Kendo & Via della Presenza*\n"
    "Allenamenti a Torino e Carmagnola. Lezione di prova gratuita.\n"
    "_Allenati alla calma nel movimento. Cresci nella disciplina._",
    "\ud83c\udf3f *Shubukan Torino \u2014 Educazione marziale gentile*\n"
    "Un dojo dove crescere in consapevolezza e presenza.\n"
    "_Non solo sport: una via di armonia._",
)


def sponsor_banner() -> str:
    return random.choice(ADS)


def send_sponsor_photo() -> None:
    """Invia la foto sponsor via URL (modo stabile)."""
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": CHAT_ID,
                "photo": SHUBUKAN_IMAGE_URL,
                "caption": sponsor_banner(),
                "parse_mode": "Markdown",
            },
            timeout=15,
        )
        if not r.ok:
            log(f"\u26a0\ufe0f Telegram photo error: {r.text}")
    except Exception as e:  # pragma: no cover - network resilience
        log(f"\u26a0\ufe0f Errore rete foto sponsor: {e}")


# === FEEDS ===
FEEDS_TECH = [
    "https://www.ilpost.it/tecnologia/feed/",
    "https://www.tomshw.it/feed/",
    "https://www.dday.it/feed",
    "https://www.hdblog.it/rss.xml",
]

FEEDS_FINANCE = [
    "https://www.ilsole24ore.com/rss/finanza.xml",
    "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
    "https://it.investing.com/rss/news_285.rss",
]

FEEDS_GAMING = [
    "https://www.eurogamer.it/feed/rss",
    "https://www.spaziogames.it/feed",
    "https://www.ign.com/rss",
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


# === UTILS ===
def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


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


def telegram_send(text: str) -> None:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        if not r.ok:
            log(f"\u26a0\ufe0f Telegram error: {r.text}")
    except Exception as e:  # pragma: no cover - network resilience
        log(f"\u26a0\ufe0f Telegram network error: {e}")


def fetch_feed_entries(feed_urls: Iterable[str]):
    urls = list(feed_urls)
    random.shuffle(urls)
    all_entries = []
    for url in urls:
        try:
            resp = requests.get(url, headers=UA_HEADERS, timeout=15)
            if not resp.ok:
                log(f"\u26a0\ufe0f HTTP {resp.status_code} su feed {url}")
                continue
            feed = feedparser.parse(resp.content)
            all_entries.extend(feed.entries)
        except Exception as ex:  # pragma: no cover - network resilience
            log(f"\u26a0\ufe0f Feed error ({url}): {ex}")
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


def send_article(feed_group: Sequence[str], brand_name: str) -> bool:
    entry = pick_fresh_entry(feed_group)
    if not entry:
        telegram_send(f"\u26a0\ufe0f Nessuna notizia trovata per *{brand_name}*.")
        return False

    title = getattr(entry, "title", "Aggiornamento")
    summary = getattr(entry, "summary", "").strip()[:400]
    link = getattr(entry, "link", "")
    comment = f"\n\ud83d\udcac *Commento AI:* {generate_comment(title, summary)}"

    msg = f"*{brand_name}*\n\n\ud83e\udde0 *{title}*\n{summary}\n\ud83d\udd17 {link}{comment}"
    telegram_send(msg)
    send_sponsor_photo()
    if link:
        SENT_LINKS.add(link)
    add_report(brand_name, title, link)
    log(f"\u2705 Inviato: {brand_name} \u2014 {title}")
    return True


# === MINI COMMENTI AI ===
def generate_comment(title: str, summary: str) -> str:  # noqa: ARG001 - future hook
    hints = [
        "Sembra una notizia destinata a far discutere.",
        "Un segnale interessante per chi segue il settore.",
        "Mostra come il mercato si stia muovendo pi\u00f9 velocemente del previsto.",
        "Un punto di svolta? Potrebbe esserlo.",
        "Vale la pena tenerla d’occhio nei prossimi giorni.",
    ]
    return random.choice(hints)


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
                "\ud83d\udea8 *ALLERTA IMPORTANTE* \u2014 fonte agenzia\n\n"
                f"\ud83d\uddd0\ufe0f *{title}*\n{summary}\n\ud83d\udd17 {link}"
            )
            telegram_send(msg)
            ALERT_SENT_IDS.add(link)
            add_report("ALERT", title, link)
            log(f"\ud83d\udea8 ALERT: {title}")
            sent_any = True
        except Exception as ex:  # pragma: no cover - network resilience
            log(f"\u26a0\ufe0f Errore invio alert: {ex}")
    return sent_any


def reset_daily() -> None:
    sent_today_hours.clear()
    REPORT.clear()
    SENT_LINKS.clear()
    ALERT_SENT_IDS.clear()
    log("\ud83d\udd04 Reset giornaliero completato.")


def hourly_brand_for(hour_idx: int) -> tuple[str, Sequence[str]]:
    group = ROTATION[hour_idx % len(ROTATION)]
    if group is FEEDS_TECH:
        return ("\ud83c\udf05 Touch Tech \u2014 Morning Spark", FEEDS_TECH)
    if group is FEEDS_FINANCE:
        return ("\ud83c\udf71 Touch Finance \u2014 Lunch Byte", FEEDS_FINANCE)
    if group is FEEDS_GAMING:
        return ("\u26a1 Touch Gaming \u2014 Brain Snack", FEEDS_GAMING)
    if group is FEEDS_CINEMA:
        return ("\ud83c\udf19 Touch Cinema \u2014 Insight", FEEDS_CINEMA)
    return ("\ud83d\udcf0 Touch Top News \u2014 Agenzie", FEEDS_AGENCIES)


# === SCHEDULER ===
def check_scheduler() -> None:
    now = datetime.now()
    h, m = now.hour, now.minute
    key = f"{h:02d}:00"

    if now.strftime("%H:%M") == "00:00":
        reset_daily()

    # check alert ogni 5 minuti
    if m % 5 == 0:
        log("\ud83d\udd0e Check allerte…")
        send_alerts()

    # pubblicazione ogni ora
    if START_HOUR <= h <= END_HOUR and m == 0 and key not in sent_today_hours:
        hour_idx = (h - START_HOUR) % len(ROTATION)
        brand_name, feeds = hourly_brand_for(hour_idx)
        telegram_send(f"\ud83d\udd50 Pubblicazione oraria: *{brand_name}*")
        send_article(feeds, brand_name)
        sent_today_hours.add(key)


def send_daily_report() -> None:
    if not REPORT:
        telegram_send("\ud83d\udcca Nessuna attivit\u00e0 oggi.")
        return
    lines = [f"\ud83d\udcca *TouchBot Report \u2014 {datetime.now().strftime('%d %B %Y')}*\n"]
    for r in REPORT:
        lines.append(f"\u2705 {r['brand']} ({r['time']})\n\u2022 {r['title']}\n\u2022 {r['link']}\n")
    telegram_send("\n".join(lines))


# === LOOP ===
def background_loop() -> None:
    log("\ud83d\ude80 Avvio TouchBot v5.1 \u2014 Smart Feeds + Alerts + Sponsor")
    while True:
        try:
            check_scheduler()
        except Exception as e:  # pragma: no cover - scheduler should keep running
            log(f"\u26a0\ufe0f Scheduler error: {e}")
        time.sleep(60)


# === ROUTES ===
@app.route("/")
def home() -> str:
    return "TouchBot v5.1 \u2014 Smart Feeds + Alerts + Sponsor \u2705"


@app.route("/static/<path:filename>")
def serve_static(filename: str):
    return send_from_directory("static", filename)


@app.route("/forza/<slot>")
def forza(slot: str) -> str:
    slot = slot.lower().strip()

    if slot in ["alert", "alerts"]:
        sent = send_alerts()
        return "\ud83d\udea8 Alert inviati." if sent else "\u2705 Nessuna allerta ora."

    # mapping categorie -> feed + nome brand
    mapping = {
        "tech": ("\ud83c\udf05 Touch Tech \u2014 Morning Spark", FEEDS_TECH),
        "finance": ("\ud83c\udf71 Touch Finance \u2014 Lunch Byte", FEEDS_FINANCE),
        "gaming": ("\u26a1 Touch Gaming \u2014 Brain Snack", FEEDS_GAMING),
        "cinema": ("\ud83c\udf19 Touch Cinema \u2014 Insight", FEEDS_CINEMA),
        "agenzie": ("\ud83d\udcf0 Touch Top News \u2014 Agenzie", FEEDS_AGENCIES),
    }

    if slot not in mapping:
        return "\u274c Slot non valido. Usa: tech, finance, gaming, cinema, agenzie, alert"

    brand_name, feeds = mapping[slot]
    telegram_send(f"\u26a1 Forzato: *{brand_name}*")
    ok = send_article(feeds, brand_name)
    return "\u2705 Inviato." if ok else "\u26a0\ufe0f Nessuna notizia trovata."


@app.route("/report")
def report_preview() -> str:
    if not REPORT:
        return "\ud83d\udce1 Nessuna attivit\u00e0 oggi."
    lines = [f"\ud83d\udcca Anteprima Report \u2014 {datetime.now().strftime('%d %B %Y')}\n"]
    for r in REPORT:
        lines.append(f"\u2022 {r['time']} \u2014 {r['brand']} \u2014 {r['title']}")
    return "\n".join(lines)


@app.route("/ads")
def ads_preview() -> str:
    return f"{sponsor_banner()}\n\nImmagine: {SHUBUKAN_IMAGE_URL}"


@app.route("/ping_telegram")
def ping_telegram() -> str:
    telegram_send("\ud83d\udc4b Touch \u00e8 vivo e operativo.")
    return "ok"


@app.route("/health")
def health() -> str:
    return "ok"


# === AVVIO ===
if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
