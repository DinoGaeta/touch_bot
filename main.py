from flask import Flask
import threading
import os, requests, feedparser, random, time
from datetime import datetime

# --- CONFIGURAZIONE ---
BOT_TOKEN = "8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g"  # <-- il tuo token
CHAT_ID = "5205240046"

ELEVEN_VOICE_ID = "OHF6JUenqAcr2JhVngrN"             # la tua voce ElevenLabs
ELEVEN_API_KEY  = os.getenv("ELEVEN_API_KEY")        # chiave salvata su Render

# JINGLE opzionale (richiede ffmpeg se abiliti ENABLE_JINGLE=1)
ENABLE_JINGLE = os.getenv("ENABLE_JINGLE", "0") == "1"
JINGLE_URL    = os.getenv("JINGLE_URL", "")  # es: https://.../touch_jingle_1s.mp3

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

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# --- TELEGRAM ---
def send_message(text: str):
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

def send_audio(file_path: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"
    try:
        with open(file_path, "rb") as f:
            r = requests.post(url, data={"chat_id": CHAT_ID}, files={"audio": f}, timeout=60)
        if r.ok:
            log("🎧 Audio inviato su Telegram.")
        else:
            log(f"⚠️ Errore invio audio: {r.text}")
    except Exception as e:
        log(f"❌ Errore apertura/invio file audio: {e}")

# --- ELEVENLABS TTS (titolo + frase gancio) ---
def generate_voice(text: str, out_mp3="voice.mp3"):
    if not ELEVEN_API_KEY:
        log("❌ Nessuna chiave ElevenLabs (ELEVEN_API_KEY).")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
    headers = {"xi-api-key": ELEVEN_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.55, "similarity_boost": 0.75}
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            log(f"⚠️ ElevenLabs error {resp.status_code}: {resp.text[:200]}")
            return None

        # salva voce base
        with open(out_mp3, "wb") as f:
            f.write(resp.content)
        log("🎙️ Voce generata.")

        # opzionale: prepend jingle (richiede pydub+ffmpeg)
        if ENABLE_JINGLE and JINGLE_URL:
            try:
                from pydub import AudioSegment
                # scarica jingle
                j = requests.get(JINGLE_URL, timeout=15)
                if j.ok:
                    with open("jingle.mp3", "wb") as jf:
                        jf.write(j.content)
                    jingle = AudioSegment.from_file("jingle.mp3", format="mp3")
                    voice  = AudioSegment.from_file(out_mp3,     format="mp3")
                    final  = jingle + voice
                    final.export("final.mp3", format="mp3")
                    log("🔔 Jingle aggiunto.")
                    return "final.mp3"
                else:
                    log("⚠️ Jingle non scaricato, invio solo voce.")
            except Exception as je:
                log(f"⚠️ Jingle disabilitato (pydub/ffmpeg): {je}")
        return out_mp3

    except Exception as e:
        log(f"❌ Errore ElevenLabs: {e}")
        return None

# --- CORE: invio rubrica + audio ---
def send_entry_with_audio(entry):
    # testo
    title = getattr(entry, "title", "Aggiornamento")
    summary = getattr(entry, "summary", "").strip()

    # messaggio testuale
    msg = f"🧠 *{title}*\n{summary[:400]}\n🔗 {getattr(entry, 'link', '')}"
    send_message(msg)

    # audio: titolo + frase gancio (prima frase del summary)
    gancio = ""
    if summary:
        # split robusto: fine frase con punto o punto + spazio
        parts = [p.strip() for p in summary.replace("\n", " ").split(". ") if p.strip()]
        gancio = parts[0] if parts else ""

    audio_text = f"{title}. {gancio}.".strip()
    audio_file = generate_voice(audio_text)
    if audio_file:
        send_audio(audio_file)

# --- LOGICA DELLE RUBRICHE ---
def check_schedule():
    now = datetime.now().strftime("%H:%M")

    if now in SCHEDULE and now not in sent_today:
        rubrica = SCHEDULE[now]
        send_message(f"{rubrica['name']} — la tua dose di curiosità tech 👇")

        for url in rubrica["feeds"]:
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (TouchBot by KitsuneLabs)'}
                feed = feedparser.parse(requests.get(url, headers=headers, timeout=15).content)
                if feed.entries:
                    entry = random.choice(feed.entries[:3])
                    send_entry_with_audio(entry)
                    log(f"✅ Notizia inviata da feed: {url}")
                else:
                    send_message(f"⚠️ Nessuna notizia trovata su {url}")
                    log(f"⚠️ Nessuna entry trovata in {url}")
            except Exception as ex:
                log(f"⚠️ Errore nel feed {url}: {ex}")

        # prompt del giorno
        send_message(random.choice(PROMPTS))
        sent_today.add(now)
        log(f"📬 Inviata rubrica: {rubrica['name']}")

    if now == "00:00":
        sent_today.clear()
        log("🔄 Reset rubriche giornaliero completato.")


# --- LOOP IN BACKGROUND ---
def background_loop():
    log("🚀 Avvio TouchBot (Touch Routine v2.2 + Voice)")
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

    for url in rubrica_trovata["feeds"]:
        try:
            response = requests.get(url, headers=headers, timeout=15)
log(f"🌐 Feed {url} → status {response.status_code}, len={len(response.text)}")
feed = feedparser.parse(response.content)

if not feed.entries:
    log(f"⚠️ Feed vuoto o non valido ({url[:40]}...)")

                entry = random.choice(feed.entries[:3])
                send_entry_with_audio(entry)
                log(f"✅ Notizia inviata da feed: {url}")
            else:
                log(f"⚠️ Nessuna entry trovata in {url}")
        except Exception as ex:
            log(f"⚠️ Errore parsing feed {url}: {ex}")

    send_message(random.choice(PROMPTS))
    return f"Rubrica {rubrica_trovata['name']} inviata ✅"


# --- BOOT ---
if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
