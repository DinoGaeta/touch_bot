#!/usr/bin/env bash
# ===============================
#  TouchBot - Render startup script
#  Versione: v5.1 – Production Stable
# ===============================

echo "[INFO] 🚀 Avvio TouchBot in modalità produzione..."
echo "[INFO] Ambiente: Render Web Service"
echo "[INFO] Avvio Gunicorn su porta 10000"

# Disattiva eventuali cache di Python
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# Assicura che le variabili di ambiente siano caricate
echo "[INFO] BOT_TOKEN: ${BOT_TOKEN:0:10}********"
echo "[INFO] CHAT_ID: ${CHAT_ID}"
echo "[INFO] START_HOUR: ${START_HOUR}"
echo "[INFO] END_HOUR: ${END_HOUR}"
echo "[INFO] SHUBUKAN_IMAGE_URL: ${SHUBUKAN_IMAGE_URL}"

# Avvio del web server Flask tramite Gunicorn
exec gunicorn touchbot:app \
    --bind 0.0.0.0:${PORT:-10000} \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -

# ===============================
# Fine avvio
# ===============================
