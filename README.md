# Touch – Daily AI Routine
![Touch AI Daily](banner_touch.png)

# 🤖 Touch – Daily AI Routine

**Touch** è un micro-bot editoriale intelligente che distribuisce notizie, curiosità e prompt ispirazionali durante la giornata seguendo i cicli cognitivi umani.

---

## Obiettivo

Creare un flusso giornaliero di contenuti tech e IA che accompagni il pubblico nei diversi momenti della giornata:
- **Mattina (08:00)** → curiosità e scoperta;
- **Pranzo (13:00)** → utilità e produttività;
- **Pomeriggio (18:00)** → ispirazione e innovazione;
- **Sera (22:00)** → riflessione e connessione emotiva.

L’idea nasce da principi di **neuromarketing**, **cronobiologia cognitiva** e **micro-engagement**, per mantenere viva l’attenzione del lettore e costruire fiducia nel tempo.

---

## Funzionalità principali

-  Raccolta automatica di notizie da feed RSS italiani (Wired, Tom’s, StartupItalia, HWUpgrade, ecc.)
-  Routine giornaliera in 4 fasce orarie con rubriche dedicate
-  Invio automatico su Telegram tramite `BOT_TOKEN` e `CHAT_ID`
-  Reset giornaliero a mezzanotte
-  Flask server per mantenere il bot sempre attivo su Render (piano gratuito)

---

## Installazione e deploy su Render

1. **Fork o clona** questo repository.  
2. Imposta nel file `main.py` le tue credenziali:
   ```python
   BOT_TOKEN = "INSERISCI_IL_TUO_TOKEN"
   CHAT_ID = "INSERISCI_IL_TUO_CHAT_ID"
