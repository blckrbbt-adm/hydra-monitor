#!/usr/bin/env python3
"""
BRG Sentinel-A — Tier 1 watchdog.
Monitors Primary. Escalates: restart → alert → Shadow promotion.
Cloudflare DNS flip: DISABLED (not configured).
"""
import time, socket, subprocess, requests, json, logging, os
from pathlib import Path

def load_env():
    env = {}
    env_file = Path("/opt/sentinel/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update(os.environ)
    return env

E = load_env()

PRIMARY_IP        = E["PRIMARY_IP"]
PRIMARY_SSH_USER  = E.get("PRIMARY_SSH_USER", "root")
SHADOW_IP         = E["SHADOW_IP"]
OPENCLAW_PORT     = int(E.get("OPENCLAW_PORT", "18789"))
HEALTH_PATH       = E.get("OPENCLAW_HEALTH_PATH", "/health")
TG_TOKEN          = E.get("TELEGRAM_TOKEN", "")
TG_CHAT           = E.get("TELEGRAM_CHAT_ID", "")
SSH_KEY           = E.get("SSH_KEY", "/opt/sentinel/sentinel_id_ed25519")
STATE_FILE        = Path("/tmp/sentinel-state.json")
CHECK_INTERVAL    = 30

T_RESTART         = 60
T_ALERT           = 120
T_PROMOTE         = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SENTINEL-A] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/var/log/sentinel/sentinel.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("sentinel")


def check_tcp(ip, port, timeout=5):
    try:
        s = socket.socket()
        s.settimeout(timeout)
        r = s.connect_ex((ip, port))
        s.close()
        return r == 0
    except Exception:
        return False


def check_http(ip, port, path, timeout=10):
    try:
        r = requests.get(f"http://{ip}:{port}{path}", timeout=timeout)
        return r.status_code < 500
    except Exception:
        return False


def ssh_cmd(ip, cmd, timeout=30):
    try:
        r = subprocess.run(
            ["ssh", "-i", SSH_KEY,
             "-o", "StrictHostKeyChecking=no",
             "-o", "ConnectTimeout=10",
             "-o", "BatchMode=yes",
             f"{PRIMARY_SSH_USER}@{ip}", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return r.returncode == 0, r.stdout + r.stderr
    except Exception as e:
        return False, str(e)


def tg(msg):
    if not TG_TOKEN or not TG_CHAT:
        log.info(f"[TG-STUB] {msg}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        log.error(f"Telegram error: {e}")


def promote_shadow():
    log.info("Promoting Shadow...")
    ok, out = ssh_cmd(SHADOW_IP, "bash /opt/brg/promote.sh")
    log.info(f"Shadow promotion: {'OK' if ok else 'FAILED'} — {out[:200]}")
    return ok


def kill_primary_openclaw():
    log.info("Attempting to stop OpenClaw on Primary (zombie prevention)...")
    ssh_cmd(PRIMARY_IP, "systemctl --user stop openclaw-gateway 2>/dev/null; true")


def primary_healthy():
    # OpenClaw port 18789 is localhost-only.
    # Health = SSH port 22 reachable + OpenClaw process running (via SSH probe)
    tcp = check_tcp(PRIMARY_IP, 22)
    if not tcp:
        log.debug("Health — SSH:False")
        return False
    # Probe OpenClaw via SSH: check if the process is active
    ok, out = ssh_cmd(PRIMARY_IP, "systemctl --user is-active openclaw-gateway")
    healthy = ok and "active" in out
    log.debug(f"Health — SSH:{tcp} OpenClaw:{healthy} ({out.strip()[:30]})")
    return healthy


def load_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return {"status": "ok", "failure_start": None, "level": 0,
            "last_ok": time.time(), "promoted": False}


def save_state(s):
    STATE_FILE.write_text(json.dumps(s))


def escalate(state):
    now = time.time()
    elapsed = now - state["failure_start"]
    level = state["level"]
    log.warning(f"Escalation — elapsed {int(elapsed)}s level {level}")

    if level == 0 and elapsed >= T_RESTART:
        log.warning("L1: attempting OpenClaw restart on Primary via SSH")
        ok, out = ssh_cmd(PRIMARY_IP, "systemctl --user restart openclaw-gateway")
        log.info(f"Restart: {'ok' if ok else 'failed'} — {out[:100]}")
        state["level"] = 1

    elif level == 1 and elapsed >= T_ALERT:
        log.warning("L2: alerting + full restart attempt")
        tg(f"🔴 <b>BRG PRIMARY DOWN</b>\nDown {int(elapsed)}s\nRestart attempted.")
        ssh_cmd(PRIMARY_IP, "systemctl --user stop openclaw-gateway; sleep 5; systemctl --user start openclaw-gateway")
        state["level"] = 2

    elif level == 2 and elapsed >= T_PROMOTE:
        log.error("L3: Primary declared dead — promoting Shadow")
        tg(f"🚨 <b>BRG PRIMARY DEAD</b>\nDown {int(elapsed//60):.0f}min\nPromoting Shadow...")
        kill_primary_openclaw()
        shadow_ok = promote_shadow()
        tg(f"{'✅' if shadow_ok else '⚠️'} <b>SHADOW PROMOTION</b>\nBoot: {'✅' if shadow_ok else '❌'}\nIP: <code>{SHADOW_IP}</code>\n<b>Manual action required.</b>")
        state = {"status": "shadow_active", "failure_start": None,
                 "level": 0, "last_ok": time.time(), "promoted": True}

    save_state(state)
    return state


def main():
    log.info(f"BRG Sentinel-A starting. Primary={PRIMARY_IP} Shadow={SHADOW_IP}")
    tg("✅ <b>BRG Sentinel-A online</b>\nMonitoring Primary.")
    state = load_state()

    while True:
        try:
            healthy = primary_healthy() if not state.get("promoted") else check_http(SHADOW_IP, OPENCLAW_PORT, HEALTH_PATH)

            if healthy:
                if state.get("status") != "ok":
                    log.info("Service recovered")
                    tg("✅ <b>BRG Service recovered</b>")
                state = {"status": "ok", "failure_start": None, "level": 0,
                         "last_ok": time.time(), "promoted": state.get("promoted", False)}
                save_state(state)
            else:
                if state.get("status") == "ok" or not state.get("failure_start"):
                    log.warning("Health check FAILED — starting failure clock")
                    state["status"] = "failing"
                    state["failure_start"] = time.time()
                    state["level"] = 0
                    save_state(state)
                else:
                    state = escalate(state)

        except Exception as e:
            log.error(f"Sentinel loop error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
