#!/usr/bin/env python3
"""
Jablotron Gate Monitor
Checks BRANA SIGNAL (PG-69118156) every 5 minutes.
If gate is ON (open), sends an alert to Discord.
"""

import os
import time
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from jablotronpy.jablotronpy import Jablotron

load_dotenv(Path(__file__).parent / ".env.local")

# ── Config ────────────────────────────────────────────────────────────────────

JAB_USER        = os.getenv("JABLOTRON_USER")
JAB_PASS        = os.getenv("JABLOTRON_PASS")
JAB_PIN         = os.getenv("JABLOTRON_PIN")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

GATE_ID         = "PG-69118156"   # BRANA SIGNAL
CHECK_INTERVAL  = 5 * 60          # 5 minutes in seconds

# ── Discord ───────────────────────────────────────────────────────────────────

def send_discord_alert(message: str):
    if not DISCORD_WEBHOOK:
        print("[Discord] No webhook URL set, skipping.")
        return
    payload = {"content": message}
    resp = requests.post(DISCORD_WEBHOOK, json=payload)
    if resp.status_code in (200, 204):
        print(f"[Discord] Alert sent.")
    else:
        print(f"[Discord] Failed to send: {resp.status_code} {resp.text}")

# ── Gate check ────────────────────────────────────────────────────────────────

def get_gate_state(jab: Jablotron, service_id: int) -> str:
    result = jab.get_programmable_gates(service_id=service_id)
    states = {s["cloud-component-id"]: s["state"] for s in result.get("states", [])}
    return states.get(GATE_ID, "unknown")

# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Initial login ─────────────────────────────────────────────────────────
    print("Logging into Jablotron Cloud...")
    try:
        jab = Jablotron(username=JAB_USER, password=JAB_PASS, pin_code=JAB_PIN)
        jab.perform_login()
        service_id = jab.get_services()[0]["service-id"]
        print(f"Service ID: {service_id}")
        print(f"Monitoring gate {GATE_ID} every {CHECK_INTERVAL // 60} minutes...\n")
    except Exception as e:
        msg = (
            f"❌ **Jablotron Monitor failed to start!**\n"
            f"🕐 Time: `{now}`\n"
            f"Error: `{e}`"
        )
        print(f"Login failed: {e}")
        send_discord_alert(msg)
        return

    # ── Polling loop ──────────────────────────────────────────────────────────
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            state = get_gate_state(jab, service_id)
            print(f"[{now}] Gate state: {state}")

            if state == "ON":
                msg = (
                    f"🚨 **Gate is OPEN!**\n"
                    f"🕐 Detected at: `{now}`\n"
                    f"Please check if the gate was left open."
                )
                send_discord_alert(msg)

        except Exception as e:
            print(f"[{now}] Error: {e} — re-logging in...")
            try:
                jab.perform_login()
                print(f"[{now}] Re-login successful.")
            except Exception as login_err:
                msg = (
                    f"⚠️ **Jablotron Monitor lost connection!**\n"
                    f"🕐 Time: `{now}`\n"
                    f"Error: `{login_err}`"
                )
                print(f"[{now}] Re-login failed: {login_err}")
                send_discord_alert(msg)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
