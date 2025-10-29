from flask import Flask
import threading
import os, requests, feedparser, random, time, json
from datetime import datetime

# --- CONFIGURAZIONE ---
BOT_TOKEN = "8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g"  # <-- il tuo token
CHAT_ID = "5205240046"

ELEVEN_VOICE_ID = "OHF6JUenqAcr2JhVngrN"  # la voce personalizzata che hai creato
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")  # chiave salvata su Render

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

# --- UTILITY LOG ---
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# --- TELEGRAM BASE ---
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

def send_audio(file_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"
    try:
        with open(file_path, "rb") as f:
            r = requests.post(url, data={"chat_id": CHAT_ID}, files={"audio": f})
        if r.ok:
            log("🎧 Audio inviato su Telegram.")
        else:
            log(f"⚠️ Errore invio audio: {r.text}")
    except Exception as e:
        log(f"❌ Errore apertura file audio: {e}")

# --- ELEVENLABS TTS ---
def generate_voice(text, filename="voice.mp3"):
    if not ELEVEN_API_KEY:
        log("❌ Nessuna chiave ElevenLabs trovata.")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.55, "similarity_boost": 0.75}
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            log(f"🎙️ Voce generata con successo: {filename}")
            return filename
        else:
            log(f"⚠️ Errore ElevenLabs: {response.status_code} - {response.text}")
    except Exception as e:
        log(f"❌ Errore richiesta ElevenLabs: {e}")
    return None

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

                    # genera e invia voce
                    # --- versione ottimizzata: solo titolo + frase gancio ---
summary = entry.summary.strip().split(". ")
gancio = summary[0] if summary else ""
audio_text = f"{entry.title}. {gancio}."

                    audio_file = generate_voice(audio_text)
                    if audio_file:
                        send_audio(audio_file)
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
    log("🚀 Avvio TouchBot (Touch Routine v2.1 + ElevenLabs Voice)")
    while True:
        check_schedule()
        time.sleep(60)  # controllo ogni minuto

# --- FLASK ROUTE ---
@app.route('/')
def home():
    return "TouchBot è attivo 🚀"

@app.route('/forza/<nome>')
def forza(nome):
    nome = nome.lower()
    for ora, rubrica in SCHEDULE.items():
        if nome in rubrica["name"].lower() or nome in ["morning", "lunch", "brain", "insight"]:
            log(f"⚡ Forzata rubrica: {rubrica['name']}")
            send_message(f"⚡ Rubrica forzata manualmente: {rubrica['name']}")
            
            for url in rubrica["feeds"]:
                feed = feedparser.parse(url)
                if feed.entries:
                    entry = random.choice(feed.entries[:3])
                    msg = f"🧠 *{entry.title}*\n{entry.summary[:400]}\n🔗 {entry.link}"
                    send_message(msg)

                    audio_text = f"{entry.title}. {entry.summary[:200]}"
                    audio_file = generate_voice(audio_text)
                    if audio_file:
                        send_audio(audio_file)
            return f"Rubrica {rubrica['name']} inviata ✅"
    return "Nome rubrica non trovato ❌"


# --- AVVIO THREAD E SERVER ---
if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
