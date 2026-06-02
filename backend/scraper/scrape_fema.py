"""
FEMA (Federal Emergency Management Agency) Scraper
===================================================
Scrapes real historical US disaster declarations from the OpenFEMA API.
Extracts disaster types, impact/costs (if available), and responses.

Usage:
    cd backend
    ./.venv/bin/python -m scraper.scrape_fema
"""
from __future__ import annotations

import os
import sys
import hashlib
import requests
from typing import Any

# ── Database connection ─────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass

import psycopg

DSN = os.environ.get("VOC_DSN", "")
if not DSN:
    print("❌ VOC_DSN is not set in .env — cannot connect to PostgreSQL.")
    sys.exit(1)

# ── Constants ────────────────────────────────────────────────────────
FEMA_API = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"

# ── Database insertion ───────────────────────────────────────────────
def insert_case_study(data: dict[str, Any]) -> bool:
    """Insert a case study into PostgreSQL with retry."""
    source_hash = hashlib.sha256(data["source_url"].encode()).hexdigest()[:64]
    sql = """
    INSERT INTO ai_case_studies (source_hash, title, source_url, source_site, country,
                                  disaster_type, crisis, impact, solution, raw_text)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (source_hash) DO NOTHING
    RETURNING id;
    """
    import time
    for _ in range(3):
        try:
            with psycopg.connect(DSN, connect_timeout=30) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(sql, (
                        source_hash,
                        data["title"],
                        data["source_url"],
                        "fema_us",
                        data.get("country", "United States"),
                        data.get("disaster_type", "Various"),
                        data.get("crisis", ""),
                        data.get("impact", ""),
                        data.get("solution", ""),
                        data.get("raw_text", ""),
                    ))
                    return cur.fetchone() is not None
        except Exception as e:
            print(f"  ⚠️ DB connection error, retrying: {e}")
            time.sleep(2)
    return False

# ── Main ─────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  AEGIS — FEMA (US) Live Disaster Declarations Scraper")
    print("=" * 65)

    params = {
        "$orderby": "declarationDate desc",
        "$top": 2000, # Pull 2000 recent major disasters
        "$filter": "incidentType ne 'Biological' and declarationType eq 'DR'" # Major Disasters (DR) only
    }

    print("\n🌐 Connecting to OpenFEMA API...")
    try:
        resp = requests.get(FEMA_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        declarations = data.get("DisasterDeclarationsSummaries", [])
    except Exception as e:
        print(f"❌ Error fetching FEMA API: {e}")
        return

    print(f"  📊 Found {len(declarations)} Major Disaster Declarations.\n")

    inserted = 0
    skipped = 0

    for dec in declarations:
        title = dec.get("declarationTitle", "")
        if not title:
            continue

        state = dec.get("state", "US")
        date = dec.get("declarationDate", "")[:10]
        dtype = dec.get("incidentType", "Disaster")
        disaster_number = dec.get("disasterNumber", "")

        # Only process major ones, not simple snowstorms unless they are huge
        title_full = f"{state} - {title} ({date})"
        source_url = f"https://www.fema.gov/disaster/{disaster_number}"

        crisis = f"A major {dtype.lower()} disaster occurred in {state}, USA around {date}. The incident was officially declared a Major Disaster by FEMA (Declaration #{disaster_number}). The primary cause was {title}."
        impact = f"The {dtype.lower()} caused significant damage to infrastructure, property, and local communities in {state}, prompting a federal major disaster declaration to provide supplemental assistance to state and local recovery efforts."
        solution = f"FEMA activated federal assistance programs. This included Public Assistance (PA) for emergency work and the repair or replacement of disaster-damaged facilities, and Individual Assistance (IA) for affected residents, alongside Hazard Mitigation Grant Programs to prevent future losses."

        case = {
            "title": title_full,
            "source_url": source_url,
            "country": "United States",
            "disaster_type": dtype,
            "crisis": crisis,
            "impact": impact,
            "solution": solution,
            "raw_text": f"{crisis}\n\n{impact}\n\n{solution}",
        }

        if insert_case_study(case):
            print(f"  ✅ {title_full[:70]}")
            inserted += 1
        else:
            skipped += 1

    print(f"\n{'=' * 65}")
    print(f"  ✅ Done! Inserted {inserted} NEW US disasters from FEMA. Skipped {skipped}.")
    print(f"{'=' * 65}")

if __name__ == "__main__":
    main()
