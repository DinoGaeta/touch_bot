from flask import Flask, send_from_directory
import threading, os, requests, feedparser, random, time
from datetime import datetime, timedelta
import time as pytime

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g")
CHAT_ID   = os.getenv("CHAT_ID",   "5205240046")

START_HOUR = int(os.getenv("START_HOUR", "7"))
END_HOUR   = int(os.getenv("END_HOUR",   "22"))

UA_HEADERS = {'User-Agent': 'TouchBot v4.4 (KitsuneLabs/Touch)'}

app = Flask(__name__)

sent_today_hours = set()
SENT_LINKS = set()
ALERT_SENT_IDS = set()
REPORT = []

# === SPONSOR: Shubukan Torino ===
SHUBUKAN_IMAGE = "https://touch-worker-8ke3.onrender.com/static/shubukan_orari.png"

ADS = [
    "🥋 *Shubukan Torino — Kendo & Via della Presenza*\nAllenamenti a Torino e Carmagnola. Lezione di prova gratuita.\n_Allenati alla calma nel movimento. Cresci nella disciplina._",
    "🌿 *Shubukan Torino — Educazione marziale gentile*\nUn dojo dove crescere in consapevolezza e presenza.\n_Non solo sport: una via di armonia._",
]

def sponsor_banner() -> str:
    return random.choice(ADS)

def send_sponsor_photo():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    caption = sponsor_banner()
    try:
        img_data = requests.get(SHUBUKAN_IMAGE, timeout=10).content
        files = {"photo": ("shubukan.png", img_data)}
        r = requests.post(
            url,
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
            files=files,
            timeout=15,
        )
        if not r.ok:
            log(f"⚠️ Errore invio foto sponsor: {r.text}")
        else:
            log("📸 Sponsor inviato.")
    except Exception as e:
        log(f"⚠️ Errore rete sponsor foto: {e}")

# === FEEDS ===
FEEDS_TECH = [
    "https://www.wired.it/feed/",
    "https://www.ilpost.it/tecnologia/feed/",
    "https://www.dday.it/rss.xml",
    "https://www.hdblog.it/rss.xml",
    "https://www.tomshw.it/feed/",
    "https://www.hwupgrade.it/news/rss/",
]

FEEDS_FINANCE = [
    "https://www.quifinanza.it/feed-rss/",
    "https://www.milanofinanza.it/rss/news.xml",
    "https://www.money.it/feed",
    "https://www.wallstreetitalia.com/feed/",
    "https://www.investireoggi.it/feed/",
]

FEEDS_GAMING = [
    "https://www.eurogamer.it/feed/rss",
    "https://multiplayer.it/rss/notizie/",
    "https://www.spaziogames.it/feed/",
    "https://www.everyeye.it/rss/notizie",
]

FEEDS_CINEMA = [
    "https://www.badtaste.it/feed/cinema/",
    "https://movieplayer.it/rss/news/",
    "https://www.comingsoon.it/rss/news/",
    "https://www.cineblog.it/feed",
]

FEEDS_AGENCIES = [
    "https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml",
    "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
    "https://www.adnkronos.com/rss.xml",
    "https://www.agi.it/rss/news.xml",
    "https://www.ilfattoquotidiano.it/feed/",
]

ROTATION = [FEEDS_TECH, FEEDS_FINANCE, FEEDS_GAMING, FEEDS_CINEMA, FEEDS_AGENCIES]
ALL_FEEDS = FEEDS_TECH + FEEDS_FINANCE + FEEDS_GAMING + FEEDS_CINEMA + FEEDS_AGENCIES

ALERT_KEYWORDS = [
    "ultim'ora", "breaking", "allerta", "allarme", "urgente", "attentato",
    "terremoto", "guerra", "missili", "evacuazione", "blackout", "cyberattacco",
]

# === UTILS ===
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def hhmm():
    return datetime.now().strftime("%H:%M")

def telegram_send(text: str):
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

def fetch_feed_entries(feed_urls):
    urls = list(feed_urls)
    random.shuffle(urls)
    all_entries = []
    for url in urls:
        try:
            resp = requests.get(url, headers=UA_HEADERS, timeout=15)
            if not resp.ok:
                log(f"⚠️ Feed error: {url} → status {resp.status_code}")
                continue
            feed = feedparser.parse(resp.content)
            log(f"📰 {url} → {len(feed.entries)} entries")
            all_entries.extend(feed.entries)
        except Exception as ex:
            log(f"⚠️ Errore feed {url}: {ex}")
    return all_entries

def pick_fresh_entry(feed_group):
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

def send_article(feed_group, brand_name: str):
    entry = pick_fresh_entry(feed_group)
    if not entry:
        telegram_send(f"⚠️ Nessuna notizia trovata per *{brand_name}*.")
        log(f"❌ Nessuna notizia trovata per {brand_name}")
        return False

    title = getattr(entry, "title", "Aggiornamento")
    summary = getattr(entry, "summary", "").strip()[:400]
    link = getattr(entry, "link", "")

    msg = f"*{brand_name}*\n\n🧠 *{title}*\n{summary}\n🔗 {link}"
    telegram_send(msg)

    if datetime.now().hour % 4 == 0:
        send_sponsor_photo()

    SENT_LINKS.add(link)
    log(f"✅ Inviato: {brand_name} — {title}")
    return True

def send_alerts():
    entries = fetch_feed_entries(FEEDS_AGENCIES)
    sent_any = False
    for e in entries[:15]:
        try:
            link = getattr(e, "link", "") or getattr(e, "id", "")
            if link in ALERT_SENT_IDS:
                continue
            txt = (getattr(e, "title", "") + " " + getattr(e, "summary", "")).lower()
            if any(k in txt for k in ALERT_KEYWORDS):
                title = getattr(e, "title", "Aggiornamento").strip()
                summary = getattr(e, "summary", "").strip()[:400]
                msg = f"🚨 *ALLERTA IMPORTANTE*\n\n🗞️ *{title}*\n{summary}\n🔗 {link}"
                telegram_send(msg)
                ALERT_SENT_IDS.add(link)
                log(f"🚨 Alert inviata: {title}")
                sent_any = True
        except Exception as ex:
            log(f"⚠️ Errore alert: {ex}")
    return sent_any

def reset_daily():
    sent_today_hours.clear()
    log("🔄 Reset giornaliero completato.")

def hourly_brand_for(hour_idx: int):
    group = ROTATION[hour_idx % len(ROTATION)]
    names = {
        FEEDS_TECH: "🌅 Touch Tech — Morning Spark",
        FEEDS_FINANCE: "🍱 Touch Finance — Lunch Byte",
        FEEDS_GAMING: "⚡ Touch Gaming — Brain Snack",
        FEEDS_CINEMA: "🌙 Touch Cinema — Insight",
        FEEDS_AGENCIES: "📰 Touch Top News — Agenzie",
    }
    return (names.get(group, "Touch News"), group)

# === SCHEDULER ===
def check_scheduler():
    now = datetime.now()
    h, m = now.hour, now.minute
    key = f"{h:02d}:00"

    if now.strftime("%H:%M") == "00:00":
        reset_daily()
    if START_HOUR <= h <= END_HOUR and m == 0 and key not in sent_today_hours:
        send_alerts()
        hour_idx = (h - START_HOUR) % len(ROTATION)
        brand_name, feeds = hourly_brand_for(hour_idx)
        telegram_send(f"🕐 Pubblicazione oraria: *{brand_name}*")
        send_article(feeds, brand_name)
        sent_today_hours.add(key)

# === LOOP ===
def background_loop():
    log("🚀 Avvio TouchBot v4.4 — Full Feed Edition")
    while True:
        try:
            check_scheduler()
        except Exception as e:
            log(f"⚠️ Scheduler error: {e}")
        time.sleep(30)

# === ROUTES ===
@app.route("/")
def home():
    return "TouchBot v4.4 — Full Feed Edition attivo ✅"

@app.route("/forza/<slot>")
def forza(slot: str):
    slot = slot.lower().strip()
    if slot == "random":
        telegram_send("🎲 *Articolo casuale da tutti i feed*")
        ok = send_article(random.choice(ROTATION), "🎲 Touch Random — Daily Pick")
        return "✅ Inviato." if ok else "⚠️ Nessuna notizia trovata."

    if slot in ["alert", "alerts"]:
        sent = send_alerts()
        return "🚨 Alert inviati." if sent else "✅ Nessuna allerta ora."

    mapping = {
        "tech": FEEDS_TECH, "finance": FEEDS_FINANCE,
        "gaming": FEEDS_GAMING, "cinema": FEEDS_CINEMA, "agenzie": FEEDS_AGENCIES
    }
    names = {
        "tech": "🌅 Touch Tech — Morning Spark",
        "finance": "🍱 Touch Finance — Lunch Byte",
        "gaming": "⚡ Touch Gaming — Brain Snack",
        "cinema": "🌙 Touch Cinema — Insight",
        "agenzie": "📰 Touch Top News — Agenzie",
    }

    feeds = mapping.get(slot)
    if not feeds:
        return "❌ Slot non valido. Usa: tech, finance, gaming, cinema, agenzie, alert, random"
    brand_name = names[slot]
    telegram_send(f"⚡ Forzato: *{brand_name}*")
    ok = send_article(feeds, brand_name)
    return "✅ Inviato." if ok else "⚠️ Nessuna notizia trovata."

# === AVVIO ===
if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
