from flask import Flask
import threading, os, requests, feedparser, random, time
from datetime import datetime

# === CONFIGURAZIONE BASE ===
BOT_TOKEN = "8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g"  # <-- tuo token
CHAT_ID   = "5205240046"                                       # <-- tuo chat id

app = Flask(__name__)
sent_today = set()
REPORT = []  # ogni item: {"time":"HH:MM", "brand":"...", "title":"...", "source":"url"}

# === BRAND LIBRARY ===
BRANDS = {
    "touch_news": {
        "name": "🌅 Morning Spark — Touch Insight",
        "feeds": ["https://www.wired.it/feed/", "https://www.ilpost.it/tecnologia/feed/"],
        "prompt": "💡 Inizia con curiosità (novelty & primacy effect)."
    },
    "touch_finance": {
        "name": "🍱 Lunch Byte — Touch Finance",
        "feeds": ["https://www.ilsole24ore.com/rss/finanza.xml",
                  "https://www.ansa.it/sito/notizie/economia/economia_rss.xml"],
        "prompt": "📊 3 minuti di chiarezza (framing positivo & sense of control)."
    },
    "touch_gaming": {
        "name": "⚡ Brain Snack — Touch Gaming",
        "feeds": ["https://www.eurogamer.it/feed/rss", "https://multiplayer.it/rss/notizie/"],
        "prompt": "🎮 Appartenenza & reward prediction per la tribù gamer."
    },
    "touch_cinema": {
        "name": "🌙 Touch Insight — Cinema",
        "feeds": ["https://www.badtaste.it/feed/cinema/", "https://movieplayer.it/rss/news/"],
        "prompt": "🎬 Rilassamento narrativo & immaginazione serale."
    }
}

# === PROGRAMMAZIONE ORARIA ===
SCHEDULE = {
    "08:00": "touch_news",
    "13:00": "touch_finance",
    "18:00": "touch_gaming",
    "22:00": "touch_cinema",
}

# === ALIAS SEMANTICI ===
ALIASES = {
    "news":   "touch_news",
    "morning":"touch_news",
    "spark":  "touch_news",

    "lunch":  "touch_finance",
    "finance":"touch_finance",
    "money":  "touch_finance",

    "gaming": "touch_gaming",
    "game":   "touch_gaming",
    "brain":  "touch_gaming",

    "cinema": "touch_cinema",
    "movie":  "touch_cinema",
    "night":  "touch_cinema",
    "insight":"touch_cinema",
}

UA_HEADERS = {'User-Agent': 'Mozilla/5.0 (TouchBot v3.3 by KitsuneLabs)'}

# === UTILITY ===
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def hhmm():
    return datetime.now().strftime("%H:%M")

def send_message(text: str, chat_id: str = CHAT_ID):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if not r.ok:
            log(f"⚠️ Telegram error: {r.text}")
    except Exception as e:
        log(f"⚠️ Telegram network error: {e}")

def get_random_entry(feed_urls):
    urls = list(feed_urls)
    random.shuffle(urls)
    for url in urls:
        try:
            resp = requests.get(url, headers=UA_HEADERS, timeout=15)
            if not resp.ok or not resp.content:
                log(f"ℹ️ Feed non ok ({url}) status={resp.status_code}")
                continue
            feed = feedparser.parse(resp.content)
            if feed.entries:
                return random.choice(feed.entries[:3])
            else:
                log(f"ℹ️ Nessuna entry in {url}")
        except Exception as ex:
            log(f"⚠️ Feed error ({url}): {ex}")
    return None

def log_activity(brand_name: str, title: str, source: str):
    REPORT.append({"time": hhmm(), "brand": brand_name, "title": title, "source": source or "-"})

def send_brand_news(brand_key: str) -> bool:
    brand = BRANDS.get(brand_key)
    if not brand:
        send_message("❌ Brand non trovato.")
        return False

    entry = get_random_entry(brand["feeds"])
    if not entry:
        send_message(f"⚠️ Nessuna notizia trovata per {brand['name']}.")
        return False

    title = getattr(entry, "title", "Aggiornamento")
    summary = getattr(entry, "summary", "")[:400]
    link = getattr(entry, "link", "")

    # messaggio principale
    msg = (
        f"*{brand['name']}*\n\n"
        f"🧠 *{title}*\n{summary}\n🔗 {link}\n\n"
        f"🪶 _{brand['prompt']}_"
    )
    send_message(msg)

    # feedback immediato
    host = ""
    try:
        host = link.split("/")[2] if "://" in link else ""
    except Exception:
        pass
    feedback = f"📨 *Articolo inviato da:* `{host or 'sorgente'}`\n📝 *Titolo:* {title}"
    send_message(feedback)

    log_activity(brand['name'], title, link)
    log(f"✅ Notizia inviata per {brand['name']}")
    return True

def next_time_for(brand_key: str):
    times = sorted([t for t, b in SCHEDULE.items() if b == brand_key])
    return ", ".join(times) if times else "Nessuna programmazione"

def resolve_brand(key: str) -> str | None:
    key = (key or "").strip().lower()
    if key in BRANDS:
        return key
    return ALIASES.get(key)

# === REPORT GIORNALIERO ===
def send_daily_report():
    day = datetime.now().strftime('%d %B %Y')
    if not REPORT:
        send_message(f"📊 *TouchBot Daily Report — {day}*\n\n📭 Nessuna attività registrata oggi.")
        return
    lines = [f"📊 *TouchBot Daily Report — {day}*\n"]
    for r in REPORT:
        lines.append(f"✅ {r['brand']} ({r['time']})\n• Titolo: {r['title']}\n• Sorgente: {r['source']}\n")
    lines.append(f"⚙️ Totale rubriche inviate: {len(REPORT)}")
    send_message("\n".join(lines))

# === LOGICA AUTOMATICA ===
def check_schedule():
    now = hhmm()

    if now in SCHEDULE and now not in sent_today:
        brand_key = SCHEDULE[now]
        brand = BRANDS[brand_key]
        send_message(f"🕐 Rubrica programmata: {brand['name']}")
        send_brand_news(brand_key)
        sent_today.add(now)
        log(f"📬 Rubrica automatica {brand['name']} inviata ({now})")

    if now == "23:59":
        log("🧾 Invio report giornaliero…")
        send_daily_report()
        REPORT.clear()
        log("🧹 Report reset.")
    if now == "00:00":
        sent_today.clear()
        log("🔄 Reset rubriche giornaliero completato.")

def background_loop():
    log("🚀 Avvio TouchBot v3.3 – Pro Routine Edition")
    while True:
        check_schedule()
        time.sleep(60)

# === FLASK ROUTES ===
@app.route("/")
def home():
    return "TouchBot v3.3 – Pro Routine Edition attivo 🚀"

@app.route("/ping")
def ping():
    return "pong"

@app.route("/brands")
def list_brands():
    text = "📚 *Rubriche disponibili:*\n\n"
    for key, data in BRANDS.items():
        text += f"• `{key}` → {data['name']} (prossima: {next_time_for(key)})\n"
    text += "\nAlias rapidi: news, lunch, gaming, cinema\n"
    text += "Forza: `/forza/<brand|alias>` – es: `/forza/lunch`"
    return text

@app.route("/help")
def help_page():
    commands = [
        "/brands – Elenco rubriche e prossimi orari",
        "/forza/<brand|alias> – Invia subito una rubrica (es: /forza/lunch)",
        "/next/<brand> – Mostra la prossima programmazione",
        "/report – Mostra il report parziale del giorno",
        "/help – Lista comandi"
    ]
    return "🧭 *Comandi disponibili:*\n" + "\n".join(commands)

@app.route("/forza/<brand>")
def forza_brand(brand: str):
    resolved = resolve_brand(brand)
    if not resolved:
        return "❌ Brand non trovato. Vai su /brands per l’elenco."
    send_message(f"⚡ Rubrica forzata manualmente: {BRANDS[resolved]['name']}")
    ok = send_brand_news(resolved)
    return f"✅ Rubrica {BRANDS[resolved]['name']} inviata!" if ok else "⚠️ Nessuna notizia trovata."

@app.route("/next/<brand>")
def next_brand(brand: str):
    resolved = resolve_brand(brand)
    if not resolved:
        return "❌ Brand non trovato."
    return f"🕒 Prossima/e per {BRANDS[resolved]['name']}: {next_time_for(resolved)}"

@app.route("/report")
def on_report():
    if not REPORT:
        return f"📭 Nessuna attività registrata oggi ({datetime.now().strftime('%d %B %Y')})."
    preview = [f"📊 *Report parziale — {datetime.now().strftime('%d %B %Y')}*\n"]
    for r in REPORT:
        preview.append(f"✅ {r['brand']} ({r['time']})\n• {r['title']}\n• {r['source']}\n")
    return "\n".join(preview)

# === AVVIO ===
if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
