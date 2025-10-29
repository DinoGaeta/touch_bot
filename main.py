from flask import Flask, send_from_directory
import threading, os, requests, feedparser, random, time
from datetime import datetime, timedelta

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g")
CHAT_ID   = os.getenv("CHAT_ID", "5205240046")  # può essere ID negativo di un gruppo

START_HOUR = int(os.getenv("START_HOUR", "7"))
END_HOUR   = int(os.getenv("END_HOUR", "22"))
INTERVAL_HOURS = 3  # ogni quante ore pubblicare

UA_HEADERS = {'User-Agent': 'TouchBot v4.7 (KitsuneLabs/Touch)'}

app = Flask(__name__)

# === TRACKERS ===
LAST_POST_TIME = None
SENT_LINKS = set()
ALERT_SENT_IDS = set()
REPORT = []

# === SPONSOR: SHUBUKAN TORINO ===
SHUBUKAN_IMAGE = "https://touch-worker-8ke3.onrender.com/static/shubukan_orari.png"

ADS = [
    "🥋 *Shubukan Torino — Kendo & Via della Presenza*\n"
    "Allenamenti a Torino e Carmagnola. Lezione di prova gratuita.\n"
    "_Allenati alla calma nel movimento. Cresci nella disciplina._",

    "🌿 *Shubukan Torino — Educazione marziale gentile*\n"
    "Un dojo dove crescere in consapevolezza e presenza.\n"
    "_Non solo sport: una via di armonia._",
]

def sponsor_banner():
    return random.choice(ADS)

def send_sponsor_photo():
    """Invia la foto sponsor separata"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    caption = sponsor_banner()
    try:
        img = requests.get(SHUBUKAN_IMAGE, timeout=10).content
        r = requests.post(url, data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
                          files={"photo": img}, timeout=15)
        if not r.ok:
            log(f"⚠️ Errore invio foto sponsor: {r.text}")
    except Exception as e:
        log(f"⚠️ Errore rete sponsor: {e}")

# === FEEDS ===
FEEDS_TECH = [
    "https://www.wired.it/feed/",
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

ROTATION = [FEEDS_TECH, FEEDS_FINANCE, FEEDS_GAMING, FEEDS_CINEMA, FEEDS_AGENCIES]

ALERT_KEYWORDS = [
    "ultim'ora", "breaking", "allerta", "allarme", "urgente", "attentato",
    "terremoto", "guerra", "missili", "evacuazione", "blackout", "cyberattacco",
]

# === UTILS ===
def log(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def telegram_send(text):
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
                          timeout=10)
        if not r.ok: log(f"⚠️ Telegram error: {r.text}")
    except Exception as e:
        log(f"⚠️ Telegram network error: {e}")

def fetch_feed_entries(feed_urls):
    entries = []
    for url in feed_urls:
        try:
            resp = requests.get(url, headers=UA_HEADERS, timeout=15)
            if resp.ok:
                feed = feedparser.parse(resp.content)
                entries.extend(feed.entries)
        except Exception as ex:
            log(f"⚠️ Feed error ({url}): {ex}")
    return entries

def pick_fresh_entry(feed_group):
    entries = fetch_feed_entries(feed_group)
    random.shuffle(entries)
    for e in entries[:8]:
        link = getattr(e, "link", "")
        if link and link not in SENT_LINKS:
            return e
    return None

def send_article(feed_group, brand_name):
    entry = pick_fresh_entry(feed_group)
    if not entry:
        telegram_send(f"⚠️ Nessuna notizia trovata per *{brand_name}*.")
        return
    title = getattr(entry, "title", "Aggiornamento")
    summary = getattr(entry, "summary", "").strip()[:400]
    link = getattr(entry, "link", "")
    msg = f"*{brand_name}*\n\n🧠 *{title}*\n{summary}\n🔗 {link}\n\n👾 _Postato automaticamente da @DailyKitsuneNews_"
    telegram_send(msg)
    send_sponsor_photo()
    SENT_LINKS.add(link)
    REPORT.append({"time": datetime.now().strftime('%H:%M'), "brand": brand_name, "title": title, "link": link})
    log(f"✅ Inviato: {brand_name} — {title}")

def send_alerts():
    entries = fetch_feed_entries(FEEDS_AGENCIES)
    for e in entries[:10]:
        try:
            link = getattr(e, "link", "")
            if link in ALERT_SENT_IDS: continue
            text = (getattr(e, "title", "") + " " + getattr(e, "summary", "")).lower()
            if any(k in text for k in ALERT_KEYWORDS):
                msg = f"🚨 *ALLERTA IMPORTANTE*\n\n🗞️ *{getattr(e, 'title', 'Aggiornamento')}*\n{getattr(e, 'summary', '')[:400]}\n🔗 {link}"
                telegram_send(msg)
                ALERT_SENT_IDS.add(link)
                log(f"🚨 Alert inviato: {getattr(e, 'title', '')}")
        except Exception as ex:
            log(f"⚠️ Errore alert: {ex}")

# === LOOP ===
def background_loop():
    global LAST_POST_TIME
    log("🚀 Avvio TouchBot v4.7 — Stable Loop Edition")
    while True:
        try:
            now = datetime.now()
            if LAST_POST_TIME is None or (now - LAST_POST_TIME) >= timedelta(hours=INTERVAL_HOURS):
                if START_HOUR <= now.hour <= END_HOUR:
                    group = ROTATION[(now.hour - START_HOUR) % len(ROTATION)]
                    names = {
                        tuple(FEEDS_TECH): "🌅 Touch Tech — Morning Spark",
                        tuple(FEEDS_FINANCE): "🍱 Touch Finance — Lunch Byte",
                        tuple(FEEDS_GAMING): "⚡ Touch Gaming — Brain Snack",
                        tuple(FEEDS_CINEMA): "🌙 Touch Cinema — Insight",
                        tuple(FEEDS_AGENCIES): "📰 Touch Top News — Agenzie",
                    }
                    name = names.get(tuple(group), "TouchBot News")
                    telegram_send(f"🕐 Pubblicazione automatica: *{name}*")
                    send_article(group, name)
                    send_alerts()
                    LAST_POST_TIME = now
            time.sleep(60)
        except Exception as e:
            log(f"⚠️ Loop error: {e}")
            time.sleep(60)

# === FLASK ROUTES ===
@app.route("/")
def home():
    return "TouchBot v4.7 — Stable Loop Edition attivo ✅"

@app.route("/forza/<slot>")
def forza(slot):
    mapping = {
        "tech": FEEDS_TECH, "finance": FEEDS_FINANCE,
        "gaming": FEEDS_GAMING, "cinema": FEEDS_CINEMA, "agenzie": FEEDS_AGENCIES
    }
    feeds = mapping.get(slot)
    if not feeds: return "❌ Slot non valido. Usa: tech, finance, gaming, cinema, agenzie"
    telegram_send(f"⚡ Forzato: *{slot.upper()}*")
    send_article(feeds, f"Forzato — {slot.upper()}")
    return "✅ Inviato manualmente."

@app.route("/test")
def test():
    telegram_send("✅ TouchBot connesso e funzionante.")
    return "✅ Test inviato al gruppo/chat."

@app.route("/report")
def report():
    if not REPORT: return "📭 Nessuna attività oggi."
    return "\n".join(f"{r['time']} — {r['brand']} — {r['title']}" for r in REPORT)

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

# === AVVIO ===
if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
