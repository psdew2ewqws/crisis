"""
Wikipedia Disaster Case Studies Scraper (Direct API)
=====================================================
Uses the MediaWiki API directly (no broken library).
Scrapes major disaster pages and extracts Crisis, Impact, Solution.
"""
import os
import sys
import hashlib
import re
import time
import requests
import psycopg
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
DSN = os.environ.get("VOC_DSN", "")

WIKI_API = "https://en.wikipedia.org/w/api.php"

WIKI_DISASTERS = [
    # Already scraped (will be skipped automatically)
    "2004 Indian Ocean earthquake and tsunami",
    "2011 Tōhoku earthquake and tsunami",
    "2020 Beirut explosion",
    "2010 Haiti earthquake",
    "Hurricane Katrina",
    "Chernobyl disaster",
    "Deepwater Horizon oil spill",
    "2022 Pakistan floods",
    "2019–20 Australian bushfire season",
    "Cyclone Nargis",
    "Bhopal disaster",
    "Fukushima nuclear accident",
    "2008 Sichuan earthquake",
    "COVID-19 pandemic",
    "Cyclone Idai",
    "Hurricane Maria",
    "Flint water crisis",
    "2010 Chile earthquake",
    "2011 East Africa drought",
    "Hurricane Sandy",
    "Hurricane Harvey",
    "Spanish flu",
    "1991 Bangladesh cyclone",
    "2015 European migrant crisis",
    "Great Chinese Famine",
    "Typhoon Haiyan",
    "2005 Kashmir earthquake",

    # NEW — Middle East & Arab World
    "2023 Derna flood",
    "2023 Marrakesh–Safi earthquake",
    "2020 Beirut port explosion",
    "Syrian civil war",
    "War in Yemen",
    "Iraqi refugee crisis",
    "2021 Jordan floods",
    "2023 Türkiye–Syria earthquake",
    "Rohingya genocide",

    # NEW — Major Floods
    "2021 Germany floods",
    "2021 China floods",
    "2019 Midwest floods",
    "2010 Pakistan floods",
    "2011 Thailand floods",
    "2018 Kerala floods",
    "2019 Iran floods",
    "2022 South African floods",
    "2020 Sudan floods",
    "North Sea flood of 1953",

    # NEW — Major Earthquakes
    "1906 San Francisco earthquake",
    "1976 Tangshan earthquake",
    "1999 İzmit earthquake",
    "2001 Gujarat earthquake",
    "2003 Bam earthquake",
    "2010 Chile earthquake",
    "2011 Christchurch earthquake",
    "2016 Ecuador earthquake",
    "2023 Afghanistan earthquakes",

    # NEW — Droughts & Famines
    "1984 Ethiopian famine",
    "Sahel drought",
    "2011 Somalia famine",
    "Cape Town water crisis",
    "California drought",
    "2022 Horn of Africa drought",

    # NEW — Pandemics & Disease Outbreaks
    "2009 flu pandemic",
    "SARS outbreak",
    "2014 Ebola virus epidemic in West Africa",
    "Cholera outbreaks in Yemen",
    "Plague of Justinian",
    "Black Death",

    # NEW — Cyclones & Hurricanes
    "Hurricane Irma",
    "Hurricane Dorian",
    "Typhoon Bopha",
    "Cyclone Winston",
    "Cyclone Amphan",
    "2004 Atlantic hurricane season",

    # NEW — Industrial & Technological Disasters
    "2013 Rana Plaza collapse",
    "Texas City refinery explosion",
    "Exxon Valdez oil spill",
    "Love Canal",
    "Minamata disease",

    # NEW — Conflict & Displacement
    "Rwandan genocide",
    "Bosnian War",
    "2022 Russian invasion of Ukraine",
    "South Sudan Civil War",
    "Darfur conflict",
    "Afghan refugee crisis",
    "Somali Civil War",
    "2006 Lebanon War",

    # NEW — Asia Pacific Disasters
    "2004 Sumatra–Andaman earthquake",
    "2009 Samoa earthquake and tsunami",
    "2018 Sulawesi earthquake and tsunami",
    "2009 Typhoon Ketsana",
    "2013 Typhoon Haiyan",
    "2016 Taiwan earthquake",
    "2019 Cotabato earthquake",
    "Cyclone Gafilo",
    "2008 Myanmar Cyclone Nargis",
    "2007 Solomon Islands earthquake",
    "2010 Mentawai earthquake",

    # NEW — South & Central Asia
    "2022 Afghanistan floods",
    "2020 Assam floods",
    "2013 India floods",
    "1970 Bhola cyclone",
    "2007 South Asian floods",
    "2014 India heat wave",
    "2015 Chennai floods",

    # NEW — African Disasters
    "2019 Cyclone Idai",
    "2007 Sub-Saharan Africa floods",
    "2019 Ethiopia floods",
    "2020 East Africa floods",
    "Sahel food crisis",
    "1998 Sudan floods",
    "2020 Sahel floods",
    "2021 South Sudan floods",
    "2022 Nigeria floods",
    "Locust plague in East Africa",

    # NEW — Americas
    "1985 Mexico City earthquake",
    "1970 Ancash earthquake",
    "2010 Chile earthquake",
    "2017 Hurricane Irma",
    "2019 Amazon wildfires",
    "2021 Haiti earthquake",
    "Hurricane Mitch",
    "1998 Hurricane Georges",
    "2005 Hurricane Wilma",
    "2010 Copiapó mining accident",
    "2013 Alberta floods",

    # NEW — Europe
    "2003 European heat wave",
    "2010 Xynthia storm",
    "2013 European floods",
    "2017 Portugal wildfires",
    "2018 Attica wildfires",
    "2021 Greece wildfires",
    "2023 Greece wildfires",

    # NEW — Water & Environmental
    "Aral Sea disaster",
    "Three Gorges Dam",
    "Banqiao Dam failure",
    "2019 Venice flooding",
    "2007 United Kingdom floods",
    "Murray–Darling basin water crisis",

    # NEW — Nuclear & Industrial
    "Three Mile Island accident",
    "SL-1 accident",
    "2011 Fukushima Daiichi nuclear disaster",
    "Jilin chemical plant explosions",
    "2020 Mauritius oil spill",
    "2010 Deepwater Horizon oil spill",

    # NEW — Modern Conflicts & Displacement
    "Venezuelan refugee crisis",
    "2015 Yemeni Civil War",
    "Central African Republic conflict",
    "Lake Chad Basin crisis",
    "2021 Ethiopia Tigray conflict",
    "2020 Nagorno-Karabakh war",
    "North Korean famine",
]


SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "AegisCrisisManager/1.0 (Crisis Management Research; contact: admin@aegis.jo)"
})


def fetch_wiki_page(title: str) -> dict | None:
    """Fetch a Wikipedia page's plain text content via the API."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|info",
        "explaintext": True,
        "format": "json",
        "inprop": "url",
    }
    resp = SESSION.get(WIKI_API, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    for page_id, page_data in pages.items():
        if page_id == "-1":
            return None
        return {
            "title": page_data.get("title", title),
            "url": page_data.get("fullurl", f"https://en.wikipedia.org/wiki/{title}"),
            "content": page_data.get("extract", ""),
        }
    return None


def parse_sections(content: str) -> tuple[str, str, str]:
    """Split Wikipedia content by == Section == headers into crisis/impact/solution."""
    # Split on level-2 headers (== Header ==)
    parts = re.split(r'\n(==\s+.+?\s+==)\n', content)

    intro = parts[0].strip()[:3000]  # intro = crisis background
    impact_parts = []
    solution_parts = []

    i = 1
    while i < len(parts) - 1:
        header = parts[i].strip().lower()
        body = parts[i + 1].strip()
        i += 2

        if any(k in header for k in [
            "impact", "casualt", "damage", "death", "effect", "consequence",
            "toll", "destruction", "injur", "humanitarian"
        ]):
            impact_parts.append(body)
        elif any(k in header for k in [
            "response", "aftermath", "relief", "recovery", "reaction",
            "aid", "lesson", "reconstruction", "reform", "investigation",
            "rescue", "cleanup", "remediation", "legacy"
        ]):
            solution_parts.append(body)

    crisis = intro if intro else "No crisis description available."
    impact = "\n".join(impact_parts)[:3000] if impact_parts else "Impact details embedded in the main article text."
    solution = "\n".join(solution_parts)[:3000] if solution_parts else "Response/recovery details embedded in the main article text."

    return crisis, impact, solution


def detect_country(text: str) -> str:
    countries = [
        "Jordan", "Syria", "Lebanon", "Iraq", "Turkey", "Libya", "Yemen",
        "Pakistan", "India", "Nepal", "Bangladesh", "Indonesia", "Japan",
        "China", "Haiti", "Chile", "United States", "Australia", "Mozambique",
        "Myanmar", "Philippines", "Iran", "Mexico", "Brazil", "Ukraine",
        "Puerto Rico", "Egypt", "Ethiopia", "Somalia",
    ]
    found = [c for c in countries if c.lower() in text.lower()]
    return ", ".join(found[:3]) if found else "Global"


def detect_disaster_type(text: str) -> str:
    types = {
        "Earthquake": ["earthquake", "seismic"],
        "Tsunami": ["tsunami"],
        "Flood": ["flood", "flooding"],
        "Cyclone/Hurricane": ["cyclone", "hurricane", "typhoon"],
        "Wildfire": ["wildfire", "bushfire", "forest fire"],
        "Pandemic": ["pandemic", "epidemic", "covid"],
        "Nuclear": ["nuclear", "reactor", "meltdown", "chernobyl", "fukushima"],
        "Industrial": ["explosion", "chemical", "oil spill", "bhopal"],
        "Drought": ["drought", "water crisis"],
        "Conflict": ["war", "conflict", "refugee"],
    }
    lower = text.lower()
    found = [t for t, kw in types.items() if any(k in lower for k in kw)]
    return ", ".join(found[:2]) if found else "Various"


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
                        source_hash, data["title"], data["source_url"], "wikipedia",
                        data["country"], data["disaster_type"], data["crisis"],
                        data["impact"], data["solution"], data["raw_text"],
                    ))
                    return cur.fetchone() is not None
        except Exception as e:
            print(f"  ⚠️ DB connection error, retrying: {e}")
            time.sleep(2)
    return False


def main():
    print("=" * 60)
    print("  AEGIS — Wikipedia Live Disaster Scraper")
    print("=" * 60)

    inserted = 0
    for title in WIKI_DISASTERS:
        print(f"\n  🔍 Fetching: {title}")
        page = fetch_wiki_page(title)
        if not page or len(page["content"]) < 500:
            print(f"    ❌ Page not found or too short: {title}")
            continue

        crisis, impact, solution = parse_sections(page["content"])
        country = detect_country(page["title"] + " " + crisis[:1000])
        dtype = detect_disaster_type(page["title"] + " " + crisis[:1000])

        data = {
            "title": page["title"],
            "source_url": page["url"],
            "country": country,
            "disaster_type": dtype,
            "crisis": crisis,
            "impact": impact,
            "solution": solution,
            "raw_text": page["content"][:8000],
        }

        if insert_case_study(data):
            print(f"    ✅ Inserted: {page['title']}")
            inserted += 1
        else:
            print(f"    ⏭️  Already exists: {page['title']}")

        time.sleep(0.5)  # be polite to Wikipedia

    print(f"\n{'=' * 60}")
    print(f"  ✅ Done! Inserted {inserted} NEW case studies from Wikipedia.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
