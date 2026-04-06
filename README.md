# BRG Hydra Monitor — DNA Repository

This repository is the source of truth for BRG infrastructure configuration,
scripts, and disaster recovery assets. It is maintained by Odin and synced
automatically from the Primary VPS.

## Structure

```
config/          Infrastructure configuration snapshots
scripts/         Operational scripts (sync, watchdog, sentinel, promote)
docs/            Architecture docs and runbooks
```

## Primary VPS
- IP: 96.126.106.225
- OS: Ubuntu 24.04 LTS
- OpenClaw: user systemd unit

## Shadow VPS
- Linode ID: 95559637
- IP: 66.175.211.18
- Region: us-east
- Spec: g6-dedicated-8

## Sentinel-A
- Linode ID: 95560059
- IP: 45.79.196.179
- Region: us-southeast (Atlanta)
- Spec: g6-nanode-1

## Tier 1 Resilience
- Sync: Primary → Shadow every 5 min via rsync
- Watchdog: Primary self-check every 5 min
- Sentinel-A: External health check every 30s, 3-level escalation ladder

## Tier 2
- Coming soon
