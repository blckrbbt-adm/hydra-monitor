#!/bin/bash
# session-watchdog.sh — checks OpenClaw gateway health, restarts if down
# Runs every 5 min via cron

OPENCLAW_URL="http://localhost:18789"
LOG="/var/log/brg/watchdog.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Watchdog check" >> "$LOG"

# Check OpenClaw gateway health
if ! curl -sf "${OPENCLAW_URL}/health" > /dev/null 2>&1; then
  echo "[$TIMESTAMP] OpenClaw health FAILED — restarting user service" >> "$LOG"
  systemctl --user restart openclaw-gateway
  sleep 15
  if curl -sf "${OPENCLAW_URL}/health" > /dev/null 2>&1; then
    echo "[$TIMESTAMP] OpenClaw recovered after restart" >> "$LOG"
  else
    echo "[$TIMESTAMP] OpenClaw still down after restart — ALERT" >> "$LOG"
  fi
else
  echo "[$TIMESTAMP] OpenClaw OK" >> "$LOG"
fi

# Rotate log (keep last 500 lines)
if [ -f "$LOG" ]; then
  tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
