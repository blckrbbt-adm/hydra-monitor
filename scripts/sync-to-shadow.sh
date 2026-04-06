#!/bin/bash
# sync-to-shadow.sh — Primary → Shadow continuous sync
# Run every 5 min via cron

SHADOW_IP="66.175.211.18"
SSH_KEY="/root/.ssh/brg_shadow_sync"
LOG="/var/log/brg/sync.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

sync_dir() {
  local src=$1
  local dst=$2
  rsync -az --delete     --exclude="node_modules/"     --exclude=".git/"     --exclude="*.tmp"     --exclude="*.lock"     -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=10"     "$src" "root@$SHADOW_IP:$dst" >> "$LOG" 2>&1
  return $?
}

echo "[$TIMESTAMP] Sync start" >> "$LOG"

sync_dir /root/.openclaw/ /root/.openclaw/
RC1=$?

sync_dir /opt/brg/ /opt/brg/
RC2=$?

if [ $RC1 -eq 0 ] && [ $RC2 -eq 0 ]; then
  echo "[$TIMESTAMP] Sync OK" >> "$LOG"
else
  echo "[$TIMESTAMP] SYNC ERROR rc1=$RC1 rc2=$RC2" >> "$LOG"
fi

# Rotate log (keep last 500 lines)
if [ -f "$LOG" ]; then
  tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
