#!/usr/bin/env python3
"""
Jablotron Cloud - PG (Programmable Gate) status checker
Usage: python jablotron_pg_status.py
"""

import os
from jablotronpy.jablotronpy import Jablotron
from dotenv import load_dotenv
load_dotenv(".env.local")

# ── Credentials (edit these or use env vars) ──────────────────────────────────
USER = os.getenv("JABLOTRON_USER", "your@email.com")
PASS = os.getenv("JABLOTRON_PASS", "yourpassword")
PIN  = os.getenv("JABLOTRON_PIN",  "1234")

# ── Login ─────────────────────────────────────────────────────────────────────
print("Logging in...")
jab = Jablotron(username=USER, password=PASS, pin_code=PIN)
jab.perform_login()

# ── Get first service ─────────────────────────────────────────────────────────
services = jab.get_services()
service_id = services[0]["service-id"]
print(f"Service ID: {service_id}\n")

# ── Fetch and print PG states ─────────────────────────────────────────────────
result = jab.get_programmable_gates(service_id=service_id)
pgs = result.get("programmable-gates", [])

if not pgs:
    print("No PG outputs found for this service.")
else:
    print(f"{'ID':<6} {'Name':<25} {'State'}")
    print("-" * 45)
    for pg in pgs:
        print(f"{pg.get('pg-id'):<6} {pg.get('pg-name', 'N/A'):<25} {pg.get('pg-state', 'unknown')}")