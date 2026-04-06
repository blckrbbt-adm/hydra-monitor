# BRG Tier 1 Resilience Architecture

## Overview

Three-node topology providing automated detection and recovery from Primary VPS failure.

```
                    ┌─────────────────┐
                    │   Sentinel-A    │
                    │ 45.79.196.179   │
                    │ Atlanta (nanode)│
                    └────────┬────────┘
                             │ monitors (SSH probe every 30s)
                    ┌────────▼────────┐         ┌─────────────────┐
                    │   Primary VPS   │◄─rsync──►│   Shadow VPS    │
                    │ 96.126.106.225  │  every   │ 66.175.211.18   │
                    │ Linode us-east  │  5 min   │ Linode us-east  │
                    │ g6-dedicated-8  │          │ g6-dedicated-8  │
                    └─────────────────┘          └─────────────────┘
```

## Sentinel-A Escalation Ladder

| Level | Trigger | Action |
|-------|---------|--------|
| L0 | Probe OK | Continue monitoring |
| L1 | Failure @ 60s | SSH restart: `systemctl --user restart openclaw-gateway` |
| L2 | Failure @ 120s | Alert logged (Telegram stub — no live token) |
| L3 | Failure @ 300s | Shadow promotion triggered via SSH |

## Sync Scope
- Source: `/root/.openclaw/` (Primary)
- Destination: `root@66.175.211.18:/root/.openclaw/`
- Excludes: `node_modules/`, `.git/`, `*.tmp`, `*.lock`
- Schedule: `*/5 * * * *` via cron

## Key Files
| File | Location | Purpose |
|------|----------|---------|
| sync-to-shadow.sh | Primary: /opt/brg/ | Rsync Primary → Shadow |
| session-watchdog.sh | Primary: /opt/brg/ | Self-check OpenClaw health |
| sentinel.py | Sentinel-A: /opt/sentinel/ | External watchdog + escalation |
| promote.sh | Shadow: /opt/brg/ (planned) | Shadow → Primary promotion |

## Systemd Units
| Unit | Host | Schedule |
|------|------|----------|
| brg-sentinel.service | Sentinel-A | Persistent (auto-restart) |
| openclaw-gateway (user) | Primary | Persistent |
| cron: sync-to-shadow | Primary | */5 * * * * |
| cron: session-watchdog | Primary | */5 * * * * |
