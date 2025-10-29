from flask import Flask, send_from_directory
import threading, os, requests, feedparser, random, time, re
from datetime import datetime, timedelta
from html import unescape

BOT_TOKEN = os.getenv("BOT_TOKEN", "8253247089:XXXXXXXX")
CHAT_ID   = os.getenv("CHAT_ID", "5205240046")

UA_HEADERS = {'User-Agent': 'TouchBot v5.0 (KitsuneLabs/Touch)'}
TIMEOUT = 15
START_HOUR, END_HOUR = 7, 22

app = Flask(__name__)

SENT_LINKS = set()
ALERT_SENT_IDS = set()
REPORT = []
sent_today_hours = set()

# === SHUBUKAN TORINO ===
SHUBUKAN_IMAGE = "https://touch-worker-8ke3.onrender.com/static/shubukan_orari.png"
ADS = [
    "🥋 *Shubukan Torino — Kendo & Via della Presenza*\nAllenati alla calma nel movimento.",
    "🌿 *Shubukan Torino — Educazione marziale gentile*\nUn dojo dove crescere in consapevolezza.",
]
def sponsor_banner(): return random.choice(ADS)

# === FEEDS ===
FEEDS_TECH = [
    "https://www.wired.it/feed/",
    "https://www.tomshw.it/feed/",
    "https://www.ilpost.it/tecnologia/feed/",
]

FEEDS_FINANCE = [
    "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
    "https://quifinanza.it/feed",
    "https://it.investing.com/rss/news.rss",
    "https://it.investing.com/rss/stock_market_news.rss",
    "https://it.investing.com/rss/economic_indicators.rss",
]

FEEDS_GAMING = [
    "https://multiplayer.it/rss/notizie/",
    "https://www.everyeye.it/rss/feed.xml",
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
ALERT_KEYWORDS = ["ultim'ora", "breaking", "urgente", "attentato", "terremoto", "guerra", "blackout"]

# === COMMENTI TEMATICI ===
COMMENTS = {
    "tech": [
        "💬 *Jarvis Insight:* La tecnologia non dorme mai, ma a volte serve saper disconnettersi.",
        "💬 *Jarvis Insight:* Ogni innovazione è un rischio calcolato. Ma chi non rischia, resta indietro.",
        "💬 *Jarvis Insight:* L’intelligenza artificiale non sostituisce: amplifica chi sa usarla bene.",
    ],
    "finance": [
        "💬 *Jarvis Insight:* I mercati reagiscono più all’incertezza che ai dati reali.",
        "💬 *Jarvis Insight:* Investire oggi è più una questione di lucidità che di coraggio.",
        "💬 *Jarvis Insight:* Ogni correzione di mercato è una lezione travestita da opportunità.",
    ],
    "gaming": [
        "💬 *Jarvis Insight:* Il gioco non è fuga, ma allenamento per la mente moderna.",
        "💬 *Jarvis Insight:* I gamer sono gli strateghi del nuovo secolo.",
    ],
    "cinema": [
        "💬 *Jarvis Insight:* Il cinema riflette ciò che non sappiamo ancora dire.",
        "💬 *Jarvis Insight:* Ogni film è un sogno condiviso — e i sogni, si sa, cambiano il mondo.",
    ],
    "agenzie": [
        "💬 *Jarvis Insight:* L’informazione è potere solo se resta libera.",
        "💬 *Jarvis Insight:* Leggere le notizie non basta: serve saperle ascoltare.",
    ],
}

def log(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def strip_html(s):
    if not s: return ""
    s = unescape(s)
    s = re.sub(r"<.*?>", "", s)
    return s.strip()

def first_summary(entry):
    for key in ["summary", "description"]:
        v = getattr(entry, key, "") or entry.get(key, "")
        if isinstance(v, str) and v.strip():
            return strip_html(v)
    if hasattr(entry, "content") and entry.content:
        c0 = entry.content[0]
        v = c0.get("value", "") if isinstance(c0, dict) else ""
        return strip_html(v)
    return ""

def telegram_send(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
        headers = {"User-Agent": "TouchBot v5.0 (KitsuneLabs)"}
        r = requests.post(url, data=payload, headers=headers, timeout=15, verify=True)
        log(f"📡 Telegram → {r.status_code}: {r.reason}")
        if not r.ok:
            log(f"⚠️ Telegram response: {r.text}")
        else:
            log("✅ Messaggio inviato con successo su Telegram.")
    except requests.exceptions.RequestException as e:
        log(f"❌ Errore rete Telegram: {e}")

def fetch_feed_entries(feed_urls):
    entries = []
    for url in feed_urls:
        try:
            resp = requests.get(url, headers=UA_HEADERS, timeout=TIMEOUT)
            if resp.ok:
                feed = feedparser.parse(resp.content)
                entries.extend(feed.entries)
                log(f"📥 {url} → {len(feed.entries)} item")
        except Exception as e:
            log(f"⚠️ Feed error ({url}): {e}")
    return entries

def pick_fresh_entry(feed_group):
    entries = fetch_feed_entries(feed_group)
    random.shuffle(entries)
    for e in entries[:10]:
        link = getattr(e, "link", "")
        if link and link not in SENT_LINKS:
            return e
    return None

def comment_for(brand):
    key = "tech" if "Tech" in brand else \
          "finance" if "Finance" in brand else \
          "gaming" if "Gaming" in brand else \
          "cinema" if "Cinema" in brand else "agenzie"
    return random.choice(COMMENTS.get(key, [""]))

def send_article(feed_group, brand):
    entry = pick_fresh_entry(feed_group)
    if not entry:
        telegram_send(f"⚠️ Nessuna notizia trovata per *{brand}*.")
        return

    title = getattr(entry, "title", "Aggiornamento").strip()
    link  = getattr(entry, "link", "") or getattr(entry, "id", "")
    summary = first_summary(entry)
    comment = comment_for(brand)
    msg = f"*{brand}*\n\n🧠 *{title}*\n{summary[:400]}\n🔗 {link}\n\n{comment}"
    telegram_send(msg)
    SENT_LINKS.add(link)
    log(f"✅ Inviato: {brand} — {title}")

def background_loop():
    log("🚀 Avvio TouchBot v5.0 — Smart Feeds + Comment Insight Edition")
    while True:
        now = datetime.now()
        h, m = now.hour, now.minute
        if START_HOUR <= h <= END_HOUR and m == 0 and h not in sent_today_hours:
            group = ROTATION[(h - START_HOUR) % len(ROTATION)]
            names = {
                tuple(FEEDS_TECH): "🌅 Touch Tech — Morning Spark",
                tuple(FEEDS_FINANCE): "🍱 Touch Finance — Lunch Byte",
                tuple(FEEDS_GAMING): "⚡ Touch Gaming — Brain Snack",
                tuple(FEEDS_CINEMA): "🌙 Touch Cinema — Insight",
                tuple(FEEDS_AGENCIES): "📰 Touch Top News — Agenzie",
            }
            brand = names.get(tuple(group), "TouchBot News")
            send_article(group, brand)
            sent_today_hours.add(h)
        time.sleep(60)

@app.route("/")
def home(): return "TouchBot v5.0 — Smart Feeds + Comment Insight Edition ✅"

@app.route("/forza/<slot>")
def forza(slot):
    mapping = {
        "tech": FEEDS_TECH, "finance": FEEDS_FINANCE,
        "gaming": FEEDS_GAMING, "cinema": FEEDS_CINEMA, "agenzie": FEEDS_AGENCIES
    }
    feeds = mapping.get(slot)
    if not feeds: return "❌ Slot non valido."
    brand = {
        "tech": "🌅 Touch Tech — Morning Spark",
        "finance": "🍱 Touch Finance — Lunch Byte",
        "gaming": "⚡ Touch Gaming — Brain Snack",
        "cinema": "🌙 Touch Cinema — Insight",
        "agenzie": "📰 Touch Top News — Agenzie"
    }[slot]
    send_article(feeds, brand)
    return "✅ Notizia inviata manualmente."

if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
