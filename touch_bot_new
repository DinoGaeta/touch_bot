import requests, feedparser, random, time, json, os
from datetime import datetime

# --- CONFIG ---
BOT_TOKEN = "8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g"
CHAT_ID = "5205240046"  # solo numero o @canale
FEEDS = [
    "https://www.wired.it/feed/",
    "https://www.ilsole24ore.com/rss/tecnologia--tecnologie.xml",
    "https://www.hwupgrade.it/news/rss/",
    "https://tech.everyeye.it/rss/notizie/",
    "https://www.tomshw.it/feed/",
    "https://www.ai4business.it/feed/",
    "https://www.startupitalia.eu/feed",
    "https://www.cybersecurity360.it/feed/"
]

# --- PROMPTS DEL GIORNO ---
PROMPTS = [
    "🔧 IT: Spiega un concetto complesso come se parlassi a un bambino.\n🔧 EN: Explain a complex concept as if to a child.",
    "🧠 IT: Scrivi 3 prompt per generare idee di startup.\n🧠 EN: Write 3 prompts to generate startup ideas.",
    "💬 IT: Analizza il tono emotivo di un testo.\n💬 EN: Analyze the emotional tone of a text.",
    "🎨 IT: Crea un prompt per un'immagine ispirata alla tecnologia e alla natura.\n🎨 EN: Create a prompt for an image blending technology and nature.",
    "⚙️ IT: Suggerisci 3 modi per migliorare la produttività usando IA.\n⚙️ EN: Suggest 3 ways to improve productivity using AI."
]

# --- FUNZIONI ---

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    r = requests.post(url, data=payload)
    if not r.ok:
        log(f"❌ Errore Telegram: {r.text}")
    else:
        log("✅ Messaggio inviato.")

def get_news():
    all_entries = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:2]:
                all_entries.append({
                    "title": e.title,
                    "summary": e.get("summary", "")[:400],
                    "link": e.link
                })
        except Exception as ex:
            log(f"Errore nel feed {url}: {ex}")
    return all_entries

def translate_to_it(text):
    try:
        r = requests.post(
            "https://libretranslate.com/translate",
            data={
                "q": text,
                "source": "en",
                "target": "it",
                "format": "text"
            },
            timeout=10
        )
        if r.ok:
            return r.json()["translatedText"]
    except Exception as e:
        log(f"⚠️ Traduzione fallita: {e}")
    return text

def summarize(entry):
    title = entry["title"]
    summary_en = entry["summary"]
    link = entry["link"]

    # Traduzione automatica
    summary_it = translate_to_it(summary_en)

    msg = (
        f"🧠 *{title}*\n"
        f"🇮🇹 {summary_it}\n\n"
        f"🌍 {summary_en}\n"
        f"🔗 {link}"
    )
    return msg


def load_sent_ids():
    if os.path.exists("sent_ids.json"):
        with open("sent_ids.json", "r") as f:
            return set(json.load(f))
    return set()

def save_sent_ids(ids):
    with open("sent_ids.json", "w") as f:
        json.dump(list(ids), f)

def main():
    log("🚀 Avvio TouchBot v0.1")
    sent_ids = load_sent_ids()
    entries = get_news()

    for entry in entries:
        if entry["link"] not in sent_ids:
            msg = summarize(entry)
            send_message(msg)
            sent_ids.add(entry["link"])
            time.sleep(8)  # pausa per evitare flood
    save_sent_ids(sent_ids)

    # Prompt of the day
    PROMPTS = [
    "💡 Suggerisci 3 prompt per creare post di qualità sui social.",
    "🧠 Scrivi un prompt per chiedere a ChatGPT di spiegare un concetto tecnico in modo chiaro.",
    "⚙️ Crea un prompt per migliorare la produttività con l'intelligenza artificiale.",
    "🎨 Genera un prompt per un'immagine in stile cyberpunk ambientata a Roma.",
    "📊 Elabora un prompt per analizzare dati aziendali con IA."
]


    log("✅ Routine completata.")

# --- LOOP GIORNALIERO ---
if __name__ == "__main__":
    while True:
        main()
        log("💤 Attesa 24h...")
        time.sleep(86400)  # ogni 24 ore


