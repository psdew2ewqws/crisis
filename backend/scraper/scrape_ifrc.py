"""
IFRC GO (Red Cross) Emergency Appeals Scraper
===============================================
Scrapes real emergency appeal data from the IFRC GO API.
"""
import os
import sys
import hashlib
import requests
import psycopg
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
DSN = os.environ.get("VOC_DSN", "")

IFRC_API = "https://goadmin.ifrc.org/api/v2/appeal/"


def detect_disaster_type(dtype_name: str) -> str:
    mapping = {
        "Flood": "Flood",
        "Epidemic": "Pandemic",
        "Earthquake": "Earthquake",
        "Cyclone": "Cyclone/Hurricane",
        "Storm": "Cyclone/Hurricane",
        "Drought": "Drought",
        "Fire": "Wildfire",
        "Volcano": "Volcanic",
        "Population Movement": "Conflict",
        "Civil Unrest": "Conflict",
        "Complex Emergency": "Conflict",
        "Cold Wave": "Extreme Weather",
        "Heat Wave": "Extreme Weather",
        "Pluvial/Fluvial Flood": "Flood",
        "Surge": "Flood",
        "Tsunami": "Tsunami",
        "Flash Flood": "Flood",
        "Landslide": "Landslide",
        "Transport Accident": "Industrial",
    }
    return mapping.get(dtype_name, dtype_name or "Various")


def scrape_ifrc():
    print("=" * 60)
    print("  AEGIS — IFRC Red Cross Live API Scraper")
    print("=" * 60)

    # Fetch recent emergency appeals
    params = {
        "limit": 2000,
        "format": "json",
        "ordering": "-start_date",
    }
    print("\n🌐 Connecting to IFRC GO API...")
    resp = requests.get(IFRC_API, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    print(f"  📊 Found {len(results)} emergency appeals.\n")

    inserted = 0
    for appeal in results:
        name = appeal.get("name", "")
        if not name:
            continue

        country_data = appeal.get("country", {})
        country = country_data.get("name", "Unknown") if country_data else "Unknown"

        dtype_data = appeal.get("dtype", {})
        dtype_name = dtype_data.get("name", "") if dtype_data else ""
        disaster_type = detect_disaster_type(dtype_name)

        amount_req = appeal.get("amount_requested", 0) or 0
        amount_fund = appeal.get("amount_funded", 0) or 0
        beneficiaries = appeal.get("num_beneficiaries", 0) or 0
        start_date = appeal.get("start_date", "")
        status = appeal.get("status_display", "")
        code = appeal.get("code", "")

        source_url = f"https://go.ifrc.org/appeals/{appeal.get('id', '')}"

        crisis = (
            f"Emergency appeal '{name}' was launched by the International Federation "
            f"of Red Cross and Red Crescent Societies (IFRC) in {country}. "
            f"Disaster type: {dtype_name}. Appeal code: {code}. "
            f"Start date: {start_date[:10] if start_date else 'N/A'}. Status: {status}."
        )

        impact = (
            f"The disaster in {country} triggered an emergency response targeting "
            f"{beneficiaries:,} beneficiaries. "
            f"The IFRC requested ${amount_req:,.0f} in funding for emergency relief operations."
        )

        solution = (
            f"The IFRC mobilized ${amount_fund:,.0f} of the requested ${amount_req:,.0f} "
            f"for emergency response operations in {country}. "
            f"The Red Cross/Red Crescent deployed emergency teams for immediate relief, "
            f"including shelter, health services, water/sanitation, and livelihood support. "
            f"Society involved: {country_data.get('society_name', 'National Red Cross Society')}."
        )

        case = {
            "title": name,
            "source_url": source_url,
            "country": country,
            "disaster_type": disaster_type,
            "crisis": crisis,
            "impact": impact,
            "solution": solution,
            "raw_text": f"{crisis}\n\n{impact}\n\n{solution}",
        }

        if insert_case_study(case):
            print(f"  ✅ {name[:65]}")
            inserted += 1
        else:
            print(f"  ⏭️  Already exists: {name[:50]}")

    print(f"\n{'=' * 60}")
    print(f"  ✅ Done! Inserted {inserted} NEW appeals from IFRC Red Cross.")
    print(f"{'=' * 60}")


def insert_case_study(data: dict) -> bool:
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
                        source_hash, data["title"], data["source_url"], "ifrc_redcross",
                        data["country"], data["disaster_type"], data["crisis"],
                        data["impact"], data["solution"], data["raw_text"],
                    ))
                    return cur.fetchone() is not None
        except Exception as e:
            print(f"  ⚠️ DB connection error, retrying: {e}")
            time.sleep(2)
    return False


if __name__ == "__main__":
    scrape_ifrc()
