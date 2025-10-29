from flask import Flask, send_from_directory
import threading, os, requests, feedparser, random, time
from datetime import datetime, timedelta
import time as pytime

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8253247089:AAH6-F0rNEiOMnFTMnwWnrrTG9l_WZO2v9g")
CHAT_ID   = os.getenv("CHAT_ID",   "5205240046")

# Orari pubblicazione oraria
START_HOUR = int(os.getenv("START_HOUR", "7"))
END_HOUR   = int(os.getenv("END_HOUR", "22"))

# Header per ridurre blocchi anti-scraping
UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TouchBot/5.3",
    "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com"
}

app = Flask(__name__)

# Stato runtime
sent_today_hours = set()   # orari “HH:00” già inviati oggi
SENT_LINKS = set()         # evita duplicati
ALERT_SENT_IDS = set()     # alert già inviati
REPORT = []                # log giornaliero per /report

# === SPONSOR: Shubukan Torino ===
# Metti l'immagine in /static/shubukan_orari.png nel repo su Render
SHUBUKAN_IMAGE_URL = "https://touch-worker-8ke3.onrender.com/static/shubukan_orari.png"
ADS = [
    "🥋 *Shubukan Torino — Kendo & Via della Presenza*\n"
    "Allenamenti a Torino e Carmagnola. Lezione di prova gratuita.\n"
    "_Allenati alla calma nel movimento. Cresci nella disciplina._",

    "🌿 *Shubukan Torino — Educazione marziale gentile*\n"
    "Un dojo dove crescere in consapevolezza e presenza.\n"
    "_Non solo sport: una via di armonia._",
]

# === FEEDS STABILI (solo RSS ben formati) ===
FEEDS_TECH = [
    "https://www.wired.it/feed/",
    "https://www.hwupgrade.it/news/rss/",
    "https://tech.everyeye.it/rss/notizie/",
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

# === UTIL ===
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def hhmm():
    return datetime.now().strftime("%H:%M")

def is_recent(entry, minutes=60):
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime.fromtimestamp(pytime.mktime(entry.published_parsed))
            return datetime.now() - published <= timedelta(minutes=minutes)
    except Exception:
        pass
    return True

def matches_alert(entry):
    txt = (getattr(entry, "title", "") + " " + getattr(entry, "summary", "")).lower()
    return any(k in txt for k in ALERT_KEYWORDS)

def telegram_send(text: str):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        if not r.ok:
            log(f"⚠️ Telegram error: {r.text}")
    except Exception as e:
        log(f"⚠️ Telegram network error: {e}")

def telegram_photo(photo_url: str, caption: str = ""):
    try:
        pic = requests.get(photo_url, timeout=12)
        if not pic.ok:
            log(f"⚠️ Sponsor image HTTP {pic.status_code}")
            return
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
            files={"photo": pic.content},
            timeout=15,
        )
        if not r.ok:
            log(f"⚠️ Telegram photo error: {r.text}")
    except Exception as e:
        log(f"⚠️ Telegram photo network error: {e}")

# === FEED DOWNLOAD (robusto) ===
def fetch_feed_entries(feed_urls):
    """Scarica feed con headers ‘browser-like’. Riprova su UTF-8 se entries vuote."""
    all_entries = []
    for url in list(feed_urls):
        try:
            resp = requests.get(url, headers=UA_HEADERS, timeout=20)
            if not resp.ok:
                log(f"⚠️ Feed {url} → HTTP {resp.status_code}")
                continue
            feed = feedparser.parse(resp.content)
            log(f"📥 {url[:60]}… → {len(feed.entries)} articoli")
            if not feed.entries:
                # fallback forzando UTF-8 (alcune testate)
                feed = feedparser.parse(resp.text.encode("utf-8"))
                log(f"↩️ Retry UTF-8: {len(feed.entries)} articoli")
            all_entries.extend(feed.entries)
        except Exception as ex:
            log(f"⚠️ Feed error ({url}): {ex}")
    if not all_entries:
        log("❌ Nessun articolo valido trovato in tutti i feed del gruppo.")
    return all_entries

def pick_fresh_entry(feed_group):
    entries = fetch_feed_entries(feed_group)
    random.shuffle(entries)
    for e in entries[:12]:
        link = getattr(e, "link", "")
        title = getattr(e, "title", "").strip()
        if not title:
            continue
        if link and link in SENT_LINKS:
            continue
        return e
    return None

def add_report(brand, title, link):
    REPORT.append({"time": hhmm(), "brand": brand, "title": title, "link": link or "-"})

def sponsor_caption():
    return random.choice(ADS)

def build_comment(title: str, summary: str) -> str:
    t = (title + " " + summary).lower()
    if any(k in t for k in ["borsa", "mercat", "spread", "inflazione", "tassi"]):
        return "\n💬 *Insight:* Mercati nervosi? Curiosità e freddezza battono fretta."
    if any(k in t for k in ["gioco", "videogame", "ps5", "xbox", "nintendo"]):
        return "\n💬 *Insight:* Ogni game è un test di strategia. Qual è la tua mossa?"
    if any(k in t for k in ["film", "cinema", "trailer", "serie"]):
        return "\n💬 *Insight:* Le storie che scegliamo modellano l’immaginario."
    if any(k in t for k in ["ai", "intelligenza artificiale", "algoritmo", "openai", "modello"]):
        return "\n💬 *Insight:* L’IA è un amplificatore: della tua attenzione e dei tuoi limiti."
    return "\n💬 *Insight:* Resta curioso: ogni notizia è una finestra su un’opportunità."

def send_article(feed_group, brand_name: str):
    """Invia 1 articolo: fallback se summary mancante + commento + sponsor."""
    entry = pick_fresh_entry(feed_group)
    if not entry:
        telegram_send(f"⚠️ Nessuna notizia trovata per *{brand_name}*.")
        return False

    title = getattr(entry, "title", "Aggiornamento").strip()
    summary = getattr(entry, "summary", "").strip()
    link = getattr(entry, "link", "")

    # Fallback summary se il feed è “muto”
    if not summary:
        summary = "_Sommario non disponibile — leggi l’articolo completo sulla fonte._"

    # messaggio
    msg = f"*{brand_name}*\n\n🧠 *{title}*\n{summary[:400]}\n🔗 {link}{build_comment(title, summary)}"
    telegram_send(msg)

    # sponsor
    telegram_photo(SHUBUKAN_IMAGE_URL, sponsor_caption())

    # segna come inviato
    if link:
        SENT_LINKS.add(link)
    add_report(brand_name, title, link)
    log(f"✅ Inviato: {brand_name} — {title}")
    return True

def send_alerts():
    """Controllo allerte ogni ~5 minuti su agenzie: invia solo news recenti + keyword."""
    entries = fetch_feed_entries(FEEDS_AGENCIES)
    sent_any = False
    for e in entries[:16]:
        try:
            link = getattr(e, "link", "") or getattr(e, "id", "")
            if link in ALERT_SENT_IDS:
                continue
            if not is_recent(e, 60):
                continue
            if not matches_alert(e):
                continue

            title = getattr(e, "title", "Aggiornamento").strip()
            summary = getattr(e, "summary", "").strip()
            if not summary:
                summary = "_Sviluppo in corso — apri la fonte per i dettagli._"

            msg = f"🚨 *ALLERTA IMPORTANTE* — fonte agenzia\n\n🗞️ *{title}*\n{summary[:400]}\n🔗 {link}"
            telegram_send(msg)
            ALERT_SENT_IDS.add(link)
            add_report("ALERT", title, link)
            log(f"🚨 ALERT: {title}")
            sent_any = True
        except Exception as ex:
            log(f"⚠️ Errore invio alert: {ex}")
    return sent_any

def reset_daily():
    sent_today_hours.clear()
    REPORT.clear()
    log("🔄 Reset giornaliero completato.")

def hourly_brand_for(hour_idx: int):
    group = ROTATION[hour_idx % len(ROTATION)]
    if group is FEEDS_TECH:     return ("🌅 Touch Tech — Morning Spark", FEEDS_TECH)
    if group is FEEDS_FINANCE:  return ("🍱 Touch Finance — Lunch Byte", FEEDS_FINANCE)
    if group is FEEDS_GAMING:   return ("⚡ Touch Gaming — Brain Snack", FEEDS_GAMING)
    if group is FEEDS_CINEMA:   return ("🌙 Touch Cinema — Insight", FEEDS_CINEMA)
    return ("📰 Touch Top News — Agenzie", FEEDS_AGENCIES)

# === SCHEDULER ===
def scheduler_loop():
    """
    Ogni 30s:
      - se HH:00 tra START_HOUR..END_HOUR e non inviato: posta 1 articolo (rotazione)
      - ogni 5 minuti: check allerte
      - a mezzanotte: reset
    """
    log("🚀 Avvio TouchBot v5.3 — Smart Fallback + Comment Insight")
    last_alert_check_min = None

    while True:
        try:
            now = datetime.now()
            h, m = now.hour, now.minute
            key = f"{h:02d}:00"

            # reset a mezzanotte
            if now.strftime("%H:%M") == "00:00":
                reset_daily()

            # check allerte ogni 5 min
            if last_alert_check_min is None or (now.minute % 5 == 0 and now.minute != last_alert_check_min):
                log("🔎 Check allerte…")
                send_alerts()
                last_alert_check_min = now.minute

            # pubblicazione oraria
            if START_HOUR <= h <= END_HOUR and m == 0 and key not in sent_today_hours:
                hour_idx = (h - START_HOUR)
                brand_name, feeds = hourly_brand_for(hour_idx)
                telegram_send(f"🕐 Pubblicazione oraria: *{brand_name}*")
                send_article(feeds, brand_name)
                sent_today_hours.add(key)

        except Exception as e:
            log(f"⚠️ Scheduler error: {e}")

        time.sleep(30)

# === ROUTES ===
@app.route("/")
def home():
    return "TouchBot v5.3 — Smart Fallback + Comment Insight ✅"

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

@app.route("/ping_telegram")
def ping_telegram():
    telegram_send("✅ TouchBot online (ping).")
    return "ok"

@app.route("/forza/<slot>")
def forza(slot: str):
    """
    Forza invio manuale:
      /forza/tech | /forza/finance | /forza/gaming | /forza/cinema | /forza/agenzie | /forza/alert(s)
    """
    slot = slot.lower().strip()
    if slot in ["alert", "alerts"]:
        sent = send_alerts()
        return "🚨 Alert inviati." if sent else "✅ Nessuna allerta ora."

    mapping = {
        "tech": FEEDS_TECH, "finance": FEEDS_FINANCE,
        "gaming": FEEDS_GAMING, "cinema": FEEDS_CINEMA, "agenzie": FEEDS_AGENCIES
    }
    feeds = mapping.get(slot)
    if not feeds:
        return "❌ Slot non valido. Usa: tech, finance, gaming, cinema, agenzie, alert"

    names = {
        "tech": "🌅 Touch Tech — Morning Spark",
        "finance": "🍱 Touch Finance — Lunch Byte",
        "gaming": "⚡ Touch Gaming — Brain Snack",
        "cinema": "🌙 Touch Cinema — Insight",
        "agenzie": "📰 Touch Top News — Agenzie",
    }
    brand_name = names.get(slot, "Touch News")
    telegram_send(f"⚡ Forzato: *{brand_name}*")
    ok = send_article(feeds, brand_name)
    return "✅ Notizia inviata manualmente." if ok else f"⚠️ Nessuna notizia trovata per {brand_name}."

@app.route("/report")
def report_preview():
    if not REPORT:
        return "📭 Nessuna attività oggi."
    lines = [f"📊 Report — {datetime.now().strftime('%d %B %Y')}\n"]
    for r in REPORT:
        lines.append(f"• {r['time']} — {r['brand']}\n  {r['title']}\n  {r['link']}\n")
    return "\n".join(lines)

@app.route("/ads")
def ads_preview():
    return f"{sponsor_caption()}\n\nImmagine: {SHUBUKAN_IMAGE_URL}"

# === AVVIO ===
if __name__ == "__main__":
    threading.Thread(target=scheduler_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
