from flask import Flask
import threading
import os, requests, feedparser, random, time
from datetime import datetime

# --- CONFIGURAZIONE ---
BOT_TOKEN = "8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g"  # <-- il tuo token
CHAT_ID = "5205240046"

# --- RUBRICHE E FEED ASSOCIATI ---
SCHEDULE = {
    "08:00": {"name": "🌅 Morning Spark", "feeds": ["https://www.wired.it/feed/"]},
    "13:00": {"name": "🍱 Lunch Byte", "feeds": ["https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml"]},
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

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# --- TELEGRAM ---
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, data=payload, timeout=15)
        if r.ok:
            log("✅ Messaggio inviato.")
        else:
            log(f"❌ Errore Telegram: {r.text}")
    except Exception as e:
        log(f"⚠️ Errore di rete Telegram: {e}")

# --- INVIO NOTIZIA ---
def send_entry(entry):
    title = getattr(entry, "title", "Aggiornamento")
    summary = getattr(entry, "summary", "").strip()
    link = getattr(entry, "link", "")
    msg = f"🧠 *{title}*\n{summary[:400]}\n🔗 {link}"
    send_message(msg)

# --- LOGICA RUBRICHE ---
def check_schedule():
    now = datetime.now().strftime("%H:%M")
    if now in SCHEDULE and now not in sent_today:
        rubrica = SCHEDULE[now]
        send_message(f"{rubrica['name']} — la tua dose di curiosità tech 👇")

        for url in rubrica["feeds"]:
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (TouchBot by KitsuneLabs)'}
                response = requests.get(url, headers=headers, timeout=15)
                log(f"🌐 Feed {url} → status {response.status_code}, len={len(response.text)}")
                feed = feedparser.parse(response.content)

                if feed.entries:
                    entry = random.choice(feed.entries[:3])
                    send_entry(entry)
                    log(f"✅ Notizia inviata da feed: {url}")
                else:
                    log(f"⚠️ Nessuna entry trovata in {url}")
                    send_message(f"⚠️ Nessuna notizia trovata su {url}")
            except Exception as ex:
                log(f"⚠️ Errore nel feed {url}: {ex}")

        send_message(random.choice(PROMPTS))
        sent_today.add(now)
        log(f"📬 Inviata rubrica: {rubrica['name']}")

    if now == "00:00":
        sent_today.clear()
        log("🔄 Reset rubriche giornaliero completato.")

# --- LOOP IN BACKGROUND ---
def background_loop():
    log("🚀 Avvio TouchBot (Touch Routine v2.4 Text-Only Stable)")
    while True:
        check_schedule()
        time.sleep(60)

# --- FLASK ROUTES ---
@app.route("/")
def home():
    return "TouchBot è attivo 🚀"

@app.route("/forza/<nome>")
def forza(nome):
    nome = nome.lower()
    rubrica_trovata = None
    for _, rubrica in SCHEDULE.items():
        if nome in rubrica["name"].lower() or nome in ["morning", "lunch", "brain", "insight"]:
            rubrica_trovata = rubrica
            break

    if not rubrica_trovata:
        log("❌ Rubrica non trovata.")
        return "Nome rubrica non trovato ❌"

    log(f"⚡ Forzata rubrica: {rubrica_trovata['name']}")
    send_message(f"⚡ Rubrica forzata manualmente: {rubrica_trovata['name']}")

    headers = {'User-Agent': 'Mozilla/5.0 (TouchBot by KitsuneLabs)'}
    for url in rubrica_trovata["feeds"]:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            log(f"🌐 Feed {url} → status {response.status_code}, len={len(response.text)}")
            feed = feedparser.parse(response.content)

            if not feed.entries:
                log(f"⚠️ Feed vuoto o non valido ({url[:40]}...)")
                continue

            entry = random.choice(feed.entries[:3])
            send_entry(entry)
            log(f"✅ Notizia inviata da feed: {url}")
        except Exception as ex:
            log(f"⚠️ Errore parsing feed {url}: {ex}")

    send_message(random.choice(PROMPTS))
    return f"Rubrica {rubrica_trovata['name']} inviata ✅"

# --- AVVIO ---
if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
