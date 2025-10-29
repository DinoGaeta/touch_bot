from flask import Flask
import threading
import os
import requests
import feedparser
import random
import time
from datetime import datetime

# === CONFIGURAZIONE BASE ===
BOT_TOKEN = "8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g"
CHAT_ID = "5205240046"

app = Flask(__name__)
sent_today = set()

# === BRAND LIBRARY ===
BRANDS = {
    "touch_news": {
        "name": "🌅 Morning Spark — Touch Insight",
        "feeds": [
            "https://www.wired.it/feed/",
            "https://www.ilpost.it/tecnologia/feed/"
        ],
        "prompt": (
            "💡 Scopri come semplificare la tua giornata con l’innovazione. "
            "Rilascia dopamina anticipatoria: inizia la giornata con curiosità."
        ),
    },
    "touch_finance": {
        "name": "🍱 Lunch Byte — Touch Finance",
        "feeds": [
            "https://www.ilsole24ore.com/rss/finanza.xml",
            "https://www.ansa.it/sito/notizie/economia/economia_rss.xml"
        ],
        "prompt": (
            "📊 Riprendi il controllo: 3 minuti di chiarezza finanziaria per "
            "sentirti al centro delle decisioni."
        ),
    },
    "touch_gaming": {
        "name": "⚡ Brain Snack — Touch Gaming",
        "feeds": [
            "https://www.eurogamer.it/feed/rss",
            "https://multiplayer.it/rss/notizie/"
        ],
        "prompt": (
            "🎮 Connettiti alla tua tribù. Le notizie che un gamer deve sapere, "
            "per il piacere della scoperta e della sfida."
        ),
    },
    "touch_cinema": {
        "name": "🌙 Touch Insight — Cinema",
        "feeds": [
            "https://www.badtaste.it/feed/cinema/",
            "https://movieplayer.it/rss/news/"
        ],
        "prompt": (
            "🎬 Lasciati ispirare: dietro ogni film c’è una storia che ti "
            "somiglia. Momento di rilassamento narrativo e immaginazione "
            "serale."
        ),
    },
}

# === PROGRAMMAZIONE ORARIA ===
SCHEDULE = {
    "08:00": "touch_news",
    "13:00": "touch_finance",
    "18:00": "touch_gaming",
    "22:00": "touch_cinema",
}


# === UTILITÀ ===
def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def send_message(text: str, chat_id: str = CHAT_ID) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if not response.ok:
            log(f"⚠️ Telegram error: {response.text}")
    except Exception as exc:  # pragma: no cover - network interaction
        log(f"⚠️ Telegram network error: {exc}")


def get_random_entry(feed_urls):
    headers = {"User-Agent": "TouchBot by KitsuneLabs"}
    for url in feed_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                return random.choice(feed.entries[:3])
        except Exception as exc:  # pragma: no cover - network interaction
            log(f"⚠️ Feed error ({url}): {exc}")
    return None


def send_brand_news(brand_key: str) -> None:
    brand = BRANDS.get(brand_key)
    if not brand:
        send_message("❌ Brand non trovato.")
        return

    entry = get_random_entry(brand["feeds"])
    if not entry:
        send_message(f"⚠️ Nessuna notizia trovata per {brand['name']}.")
        return

    title = getattr(entry, "title", "Aggiornamento")
    summary = getattr(entry, "summary", "")[:400]
    link = getattr(entry, "link", "")
    msg = (
        f"*{brand['name']}*\n\n"
        f"🧠 *{title}*\n{summary}\n🔗 {link}\n\n"
        f"🪶 _{brand['prompt']}_"
    )
    send_message(msg)
    log(f"✅ Inviata notizia per {brand['name']}")


# === INTERFACCIA COMANDI ===
def send_brands_index() -> str:
    text = "📚 *Rubriche giornaliere di TouchBot:*\n\n"
    for key, data in BRANDS.items():
        text += f"• `{key}` → {data['name']}\n"
    text += "\nUsa `/forza/<brand>` per forzarne una. Esempio: `/forza/touch_finance`"
    return text


def send_help() -> str:
    commands = [
        "/start – Presentazione e scopo del bot",
        "/brands – Elenco rubriche attive e orari",
        "/forza/<brand> – Forza l’invio immediato di una rubrica",
        "/next/<brand> – Mostra la prossima pubblicazione programmata",
        "/help – Mostra questo elenco di comandi",
    ]
    return "🧭 *Comandi disponibili:*\n" + "\n".join(commands)


# === LOGICA AUTOMATICA ===
def check_schedule() -> None:
    now = datetime.now().strftime("%H:%M")
    if now in SCHEDULE and now not in sent_today:
        brand_key = SCHEDULE[now]
        brand = BRANDS[brand_key]
        send_message(f"🕐 Rubrica programmata: {brand['name']}")
        send_brand_news(brand_key)
        sent_today.add(now)
        log(f"📬 Rubrica automatica {brand['name']} inviata ({now})")

    if now == "00:00":
        sent_today.clear()
        log("🔄 Reset giornaliero completato.")


def background_loop() -> None:
    log("🚀 Avvio TouchBot v3.1 Neuromarketing Edition")
    while True:
        check_schedule()
        time.sleep(60)


# === FLASK ROUTES ===
@app.route("/")
def home() -> str:
    return "TouchBot v3.1 Neuromarketing Edition attivo 🚀"


@app.route("/brands")
def list_brands() -> str:
    return send_brands_index()


@app.route("/help")
def help_page() -> str:
    return send_help()


@app.route("/forza/<brand>")
def forza_brand(brand: str) -> str:
    if brand not in BRANDS:
        return "❌ Brand non trovato. Vai su /brands per l’elenco."
    send_message(f"⚡ Rubrica forzata manualmente: {BRANDS[brand]['name']}")
    send_brand_news(brand)
    return f"✅ Rubrica {BRANDS[brand]['name']} inviata!"


# === AVVIO ===
if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
