#!/usr/bin/env python3
"""
Jablotron Gate Monitor
Checks BRANA SIGNAL (PG-69118156) every 5 minutes.
If gate is ON (open), sends an alert to Discord.
Publishes gate state to MQTT on every poll (if MQTT_BROKER is configured).
"""

import os
import time
import requests
from pathlib import Path
from datetime import datetime
import zoneinfo

import paho.mqtt.client as mqtt

from jablotronpy.jablotronpy import Jablotron

# ── Config ────────────────────────────────────────────────────────────────────

JAB_USER        = os.getenv("JABLOTRON_USER")
JAB_PASS        = os.getenv("JABLOTRON_PASS")
JAB_PIN         = os.getenv("JABLOTRON_PIN")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

MQTT_BROKER     = os.getenv("MQTT_BROKER")
MQTT_PORT       = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC      = os.getenv("MQTT_TOPIC", "jablotron/gate/state")
MQTT_USER       = os.getenv("MQTT_USER")
MQTT_PASS       = os.getenv("MQTT_PASS")
MQTT_CLIENT_ID  = os.getenv("MQTT_CLIENT_ID", "jablotron_gate_monitor")

GATE_ID         = "PG-69118156"   # BRANA SIGNAL
CHECK_INTERVAL  = 5 * 60          # 5 minutes in seconds
TZ              = zoneinfo.ZoneInfo("Europe/Bratislava")

# ── Discord ───────────────────────────────────────────────────────────────────

def send_discord_alert(message: str):
    if not DISCORD_WEBHOOK:
        print("[Discord] No webhook URL set, skipping.")
        return
    masked = DISCORD_WEBHOOK[:40] + "..." + DISCORD_WEBHOOK[-10:]
    print(f"[Discord] Sending to: {masked}")
    payload = {"content": message}
    resp = requests.post(DISCORD_WEBHOOK, json=payload)
    if resp.status_code in (200, 204):
        print(f"[Discord] Alert sent.")
    else:
        print(f"[Discord] Failed to send: {resp.status_code} {resp.text}")

# ── MQTT ──────────────────────────────────────────────────────────────────────

def _on_mqtt_connect(_client, _userdata, _connect_flags, reason_code, _properties):
    if reason_code.is_failure:
        print(f"[MQTT] Connection failed: {reason_code}")
    else:
        print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")

def _on_mqtt_disconnect(_client, _userdata, _disconnect_flags, reason_code, _properties):
    print(f"[MQTT] Disconnected (rc={reason_code}). Will auto-reconnect.")

def setup_mqtt() -> mqtt.Client | None:
    """Connect to the MQTT broker and start the background network loop.
    Returns None if MQTT_BROKER is not configured."""
    if not MQTT_BROKER:
        print("[MQTT] MQTT_BROKER not set — MQTT publishing disabled.")
        return None

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=MQTT_CLIENT_ID,
    )
    client.on_connect    = _on_mqtt_connect
    client.on_disconnect = _on_mqtt_disconnect

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()   # background thread handles reconnects
        return client
    except Exception as e:
        print(f"[MQTT] Failed to connect to {MQTT_BROKER}:{MQTT_PORT} — {e}")
        return None

def publish_gate_state(client: mqtt.Client | None, state: str):
    """Publish gate state ('ON', 'OFF', 'unknown') to MQTT with retain=True."""
    if client is None:
        return
    result = client.publish(MQTT_TOPIC, payload=state, qos=1, retain=True)
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"[MQTT] Published '{state}' → {MQTT_TOPIC}")
    else:
        print(f"[MQTT] Publish failed (rc={result.rc})")

# ── Gate check ────────────────────────────────────────────────────────────────

def get_gate_state(jab: Jablotron, service_id: int) -> str:
    result = jab.get_programmable_gates(service_id=service_id)
    states = {s["cloud-component-id"]: s["state"] for s in result.get("states", [])}
    return states.get(GATE_ID, "unknown")

# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    masked = DISCORD_WEBHOOK[:40] + "..." + DISCORD_WEBHOOK[-10:] if DISCORD_WEBHOOK else "NOT SET"
    print(f"Discord webhook: {masked}")
    print(f"MQTT broker:     {MQTT_BROKER or 'NOT SET'}")

    mqtt_client = setup_mqtt()

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
        now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
        try:
            state = get_gate_state(jab, service_id)
            print(f"[{now}] Gate state: {state}")

            publish_gate_state(mqtt_client, state)

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
