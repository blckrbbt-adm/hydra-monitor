#!/bin/bash
# BRG Shadow VPS — Promotion Script
# Run on Shadow VPS to promote it to Primary role
# Usage: bash promote.sh
set -euo pipefail

PRIMARY_IP="96.126.106.225"
SHADOW_IP="66.175.211.18"
LOG="/var/log/brg-promote.log"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$LOG"; }

log "=== BRG Shadow → Primary Promotion ==="
log "Shadow IP: $SHADOW_IP"
log "Old Primary IP: $PRIMARY_IP"

# 1. Ensure OpenClaw gateway is not running (avoid split-brain)
log "Step 1: Stopping any stale OpenClaw processes..."
systemctl --user stop openclaw-gateway 2>/dev/null || true
sleep 2

# 2. Start OpenClaw gateway on Shadow
log "Step 2: Starting OpenClaw gateway..."
systemctl --user start openclaw-gateway
sleep 5

if systemctl --user is-active openclaw-gateway >/dev/null 2>&1; then
  log "Step 2: Gateway active — OK"
else
  log "Step 2: ERROR — gateway failed to start"
  exit 1
fi

# 3. Verify health
log "Step 3: Health check..."
if curl -sf http://localhost:18789/health >/dev/null 2>&1; then
  log "Step 3: Health OK"
else
  log "Step 3: WARNING — health endpoint not responding (may be auth-gated)"
fi

log "=== Promotion complete. Shadow is now acting as Primary. ==="
log "Next steps:"
log "  1. Update DNS / Sentinel-A PRIMARY_IP to $SHADOW_IP"
log "  2. Notify team that Primary has failed over"
log "  3. Investigate original Primary at $PRIMARY_IP"
