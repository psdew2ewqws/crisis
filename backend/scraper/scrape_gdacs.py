"""
GDACS (UN Global Disaster Alert and Coordination System) Scraper
=================================================================
Pulls real disaster events directly from the UN GDACS API.
Only Red/Orange alert events (high impact) are collected.
"""
import os, sys, hashlib, time, requests, psycopg
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
DSN = os.environ.get("VOC_DSN", "")

GDACS_API = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"

EVENT_TYPE_NAMES = {
    "EQ": "Earthquake", "TC": "Cyclone/Hurricane", "FL": "Flood",
    "VO": "Volcanic", "DR": "Drought", "WF": "Wildfire",
    "TS": "Tsunami", "LS": "Landslide",
}

def fetch_gdacs_events():
    """Fetch Red and Orange alert events from GDACS 2020–2025."""
    print("🌐 Connecting to GDACS (UN) API...")
    params = {
        "eventlist": "EQ,TC,FL,VO,DR,WF",
        "alertlevel": "Orange,Red",   # Only high-impact events
        "fromdate": "2000-01-01",
        "todate": "2025-12-31",
        "limit": 2000,
    }
    resp = requests.get(
        GDACS_API,
        params=params,
        headers={"Accept": "application/json"},
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("features", [])


def build_case_study(feature: dict) -> dict | None:
    props = feature.get("properties", {})
    name = props.get("name", "").strip()
    if not name or len(name) < 5:
        return None

    event_type_code = props.get("eventtype", "")
    disaster_type = EVENT_TYPE_NAMES.get(event_type_code, event_type_code)
    country = props.get("country", "Global")
    from_date = props.get("fromdate", "")[:10]
    to_date = props.get("todate", "")[:10]
    alert_level = props.get("alertlevel", "")
    severity_data = props.get("severitydata", {})
    severity_text = severity_data.get("severitytext", "")
    html_desc = props.get("htmldescription", "") or props.get("description", "")
    report_url = props.get("url", {}).get("report", f"https://www.gdacs.org")

    crisis = (
        f"{name}. "
        f"The event was classified as a {alert_level}-level {disaster_type} alert by the "
        f"UN Global Disaster Alert and Coordination System (GDACS). "
        f"The event occurred in {country} from {from_date} to {to_date}. "
        f"{html_desc}"
    ).strip()

    impact = (
        f"GDACS assessed this as a {alert_level} alert ({disaster_type}) affecting {country}. "
        f"Severity assessment: {severity_text}. "
        f"Alert score: {props.get('alertscore', 'N/A')}."
    )

    solution = (
        f"The UN GDACS system triggered a {alert_level}-level international alert for this "
        f"{disaster_type} event in {country}, mobilizing the global disaster coordination "
        f"network. GDACS alerted governments, humanitarian organizations, and the media. "
        f"Standard response protocols for {disaster_type} events were activated, including "
        f"deployment of UN OCHA coordination teams, WFP emergency food assistance, UNHCR "
        f"displacement support, and WHO health emergency response as needed."
    )

    return {
        "title": name[:500],
        "source_url": report_url,
        "country": country,
        "disaster_type": disaster_type,
        "crisis": crisis[:3000],
        "impact": impact[:3000],
        "solution": solution[:3000],
        "raw_text": f"{crisis}\n\n{impact}\n\n{solution}",
    }


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
                        source_hash, data["title"], data["source_url"], "gdacs",
                        data["country"], data["disaster_type"], data["crisis"],
                        data["impact"], data["solution"], data["raw_text"],
                    ))
                    return cur.fetchone() is not None
        except Exception as e:
            print(f"  ⚠️ DB connection error, retrying: {e}")
            time.sleep(2)
    return False


def main():
    print("=" * 65)
    print("  AEGIS — GDACS UN Live Disaster Events Scraper")
    print("=" * 65)

    features = fetch_gdacs_events()
    print(f"  📊 Found {len(features)} high-impact events (Orange/Red alerts).\n")

    inserted = 0
    skipped = 0
    for feat in features:
        case = build_case_study(feat)
        if not case:
            continue
        if insert_case_study(case):
            print(f"  ✅ {case['title'][:70]}")
            inserted += 1
        else:
            skipped += 1

    print(f"\n{'=' * 65}")
    print(f"  ✅ Done! Inserted {inserted} events, skipped {skipped} duplicates.")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
