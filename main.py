from flask import Flask
import threading
import os, requests, feedparser, random, time, json
from datetime import datetime

# --- CONFIGURAZIONE ---
BOT_TOKEN = "8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g"
CHAT_ID = "5205240046"

# --- RUBRICHE E FEED ASSOCIATI ---
SCHEDULE = {
    "08:00": {"name": "🌅 Morning Spark", "feeds": ["https://www.wired.it/feed/"]},
    "13:00": {"name": "🍱 Lunch Byte", "feeds": ["https://www.hwupgrade.it/news/rss/"]},
    "18:00": {"name": "⚡ Brain Snack", "feeds": ["https://www.startupitalia.eu/feed"]},
    "22:00": {"name": "🌙 Touch Insight", "feeds": ["https://www.tomshw.it/feed/"]}
}

# --- PROMPTS ISPIRAZIONALI ---
PROMPTS = [
    "💡 Cosa puoi automatizzare oggi per risparmiare 10 minuti domani?",
    "🧠 Qual è l’idea più piccola che potrebbe cambiare la tua giornata?",
    "⚙️ Se avessi un assistente IA perfetto, cosa gli faresti fare adesso?",
    "🎨 Immagina la tecnologia come arte. Cosa creerebbe di bello oggi?",
    "🌍 Oggi prova a spiegare un concetto complesso con una metafora semplice."
]

app = Flask(__name__)
sent_today = set()

# --- FUNZIONI BASE ---
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.ok:
            log("✅ Messaggio inviato.")
        else:
            log(f"❌ Errore Telegram: {r.text}")
    except Exception as e:
        log(f"⚠️ Errore di rete: {e}")

# --- LOGICA DELLE RUBRICHE ---
def check_schedule():
    now = datetime.now().strftime("%H:%M")
    if now in SCHEDULE and now not in sent_today:
        rubrica = SCHEDULE[now]
        intro = f"{rubrica['name']} — la tua dose di curiosità tech 👇"
        send_message(intro)

        for url in rubrica["feeds"]:
            try:
                feed = feedparser.parse(url)
                if feed.entries:
                    entry = random.choice(feed.entries[:3])
                    msg = f"🧠 *{entry.title}*\n{entry.summary[:400]}\n🔗 {entry.link}"
                    send_message(msg)
            except Exception as ex:
                log(f"Errore nel feed {url}: {ex}")

        # prompt del giorno a caso
        send_message(random.choice(PROMPTS))
        sent_today.add(now)
        log(f"Inviata rubrica: {rubrica['name']}")

    # reset giornaliero
    if now == "00:00":
        sent_today.clear()
        log("🔄 Reset rubriche giornaliero completato.")

# --- LOOP IN BACKGROUND ---
def background_loop():
    log("🚀 Avvio TouchBot (Touch Routine v1.0)")
    while True:
        check_schedule()
        time.sleep(60)  # controllo ogni minuto

# --- FLASK ROUTE ---
@app.route('/')
def home():
    return "TouchBot è attivo 🚀"

# --- AVVIO THREAD E SERVER ---
if __name__ == "__main__":
    threading.Thread(target=background_loop).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

