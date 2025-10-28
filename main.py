from flask import Flask
import threading
import os, requests, feedparser, random, time, json, datetime

app = Flask(__name__)

BOT_TOKEN = os.getenv("8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g")
CHAT_ID = os.getenv("5205240046")

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

PROMPTS = [
    "💡 Suggerisci 3 prompt per creare post di qualità sui social.",
    "🧠 Scrivi un prompt per chiedere a ChatGPT di spiegare un concetto tecnico in modo chiaro.",
    "⚙️ Crea un prompt per migliorare la produttività con l'intelligenza artificiale.",
    "🎨 Genera un prompt per un'immagine in stile cyberpunk ambientata a Roma.",
    "📊 Elabora un prompt per analizzare dati aziendali con IA."
]

def log(msg): 
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    r = requests.post(url, data=payload)
    if r.ok:
        log("✅ Messaggio inviato.")
    else:
        log(f"❌ Errore Telegram: {r.text}")

def get_news():
    all_entries = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:2]:
                title = e.get("title", "")
                summary = e.get("summary", e.get("description", ""))[:400]
                link = e.get("link", "")
                if title and link:
                    all_entries.append({"title": title, "summary": summary, "link": link})
        except Exception as ex:
            log(f"Errore nel feed {url}: {ex}")
    return all_entries

def main():
    log("🚀 Avvio TouchBot (Render version)")
    entries = get_news()
    count = 0
    for entry in entries:
        msg = f"🧠 *{entry['title']}*\n{entry['summary']}\n🔗 {entry['link']}"
        send_message(msg)
        count += 1
        time.sleep(5)
    send_message(f"✅ Inviate {count} notizie italiane.\n✨ Prompt del Giorno:\n{random.choice(PROMPTS)}")
    log("✅ Routine completata.")

# thread per il bot
def background_loop():
    while True:
        main()
        log("💤 Attesa 24h...")
        time.sleep(86400)

@app.route('/')
def home():
    return "TouchBot è attivo 🚀"

if __name__ == "__main__":
    threading.Thread(target=background_loop).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

