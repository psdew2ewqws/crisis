"""
WHO (World Health Organization) Disease Outbreak News Scraper
==============================================================
Scrapes Disease Outbreak News (DON) and emergency situation reports
from the WHO website, extracts (Crisis, Impact, Solution) from each,
and stores the structured data in PostgreSQL (voc360).

WHO does not have an official public API, so we scrape the DON listing
page and individual report pages.

Usage:
    cd backend
    ./.venv/bin/python -m scraper.scrape_who
"""
from __future__ import annotations

import os
import re
import sys
import hashlib
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

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
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

WHO_BASE = "https://www.who.int"

# WHO DON listing pages and emergency situation report pages
WHO_DON_URLS = [
    f"{WHO_BASE}/emergencies/disease-outbreak-news",
]

# WHO emergency appeal / situation report search pages
WHO_EMERGENCY_URLS = [
    f"{WHO_BASE}/emergencies/situations",
]

MAX_ARTICLES = 500
DELAY_BETWEEN_REQUESTS = 1  # seconds — be polite

# ── SQL ──────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ai_case_studies (
    id              SERIAL PRIMARY KEY,
    source_hash     VARCHAR(64) UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    source_url      TEXT,
    source_site     VARCHAR(50) DEFAULT 'who',
    country         TEXT,
    disaster_type   TEXT,
    crisis          TEXT,
    impact          TEXT,
    solution        TEXT,
    raw_text        TEXT,
    scraped_at      TIMESTAMPTZ DEFAULT NOW()
);
"""


def create_table():
    with psycopg.connect(DSN) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)


# ── Scraping helpers ─────────────────────────────────────────────────
def fetch_page(url: str) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            return BeautifulSoup(resp.text, "html.parser")
        else:
            print(f"  ⚠️  HTTP {resp.status_code} for {url}")
            return None
    except Exception as e:
        print(f"  ❌ Error fetching {url}: {e}")
        return None


def extract_don_links(soup: BeautifulSoup) -> list[str]:
    """Extract Disease Outbreak News article links from the listing page."""
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Match DON report links
        if "/emergencies/disease-outbreak-news/" in href and href != "/emergencies/disease-outbreak-news":
            full_url = href if href.startswith("http") else WHO_BASE + href
            if full_url not in links and "who.int" in full_url:
                links.append(full_url)
    return links


def extract_emergency_links(soup: BeautifulSoup) -> list[str]:
    """Extract emergency situation report links."""
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if any(pattern in href for pattern in [
            "/emergencies/situations/", "/emergencies/disease-outbreak-news/",
            "/news/item/", "/publications/i/item/"
        ]):
            full_url = href if href.startswith("http") else WHO_BASE + href
            if full_url not in links and "who.int" in full_url:
                links.append(full_url)
    return links


def extract_article_content(soup: BeautifulSoup, url: str) -> dict[str, Any] | None:
    """Extract structured content from a WHO article page."""
    # Title
    title_tag = soup.find("h1") or soup.find("title")
    if not title_tag:
        return None
    title = title_tag.get_text(strip=True)
    if len(title) < 10:
        return None

    # Remove common suffixes
    title = re.sub(r'\s*[-–|]\s*WHO$', '', title).strip()

    # Main body text
    body_text = ""
    for selector in [
        "article", ".sf-detail-body-wrapper", ".content-block",
        ".field--name-body", ".node__content", "main"
    ]:
        if "." in selector or "#" in selector:
            container = soup.select_one(selector)
        else:
            container = soup.find(selector)
        if container:
            body_text = container.get_text(separator="\n", strip=True)
            break

    if not body_text or len(body_text) < 150:
        paragraphs = soup.find_all("p")
        body_text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)

    if len(body_text) < 150:
        return None

    raw_text = body_text[:12000]

    crisis, impact, solution = extract_crisis_impact_solution(title, raw_text)
    country = detect_country(title + " " + raw_text[:2000])
    disaster_type = detect_disaster_type(title + " " + raw_text[:2000])

    return {
        "title": title[:500],
        "source_url": url,
        "country": country,
        "disaster_type": disaster_type,
        "crisis": crisis,
        "impact": impact,
        "solution": solution,
        "raw_text": raw_text[:8000],
    }


def extract_crisis_impact_solution(title: str, text: str) -> tuple[str, str, str]:
    """Extract crisis, impact, and solution from article text."""
    paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]

    crisis_parts = []
    impact_parts = []
    solution_parts = []

    crisis_keywords = [
        "crisis", "disaster", "earthquake", "flood", "drought", "pandemic",
        "outbreak", "conflict", "emergency", "hazard", "storm", "cyclone",
        "disease", "virus", "infection", "epidemic", "pathogen", "strain",
        "variant", "case", "confirmed", "detected", "reported", "surveillance",
    ]
    impact_keywords = [
        "impact", "affect", "damage", "loss", "casualt", "displac", "injur",
        "death", "destruction", "econom", "cost", "billion", "million",
        "mortality", "morbidity", "hospitaliz", "fatality", "toll",
        "health system", "overwhelm", "capacity", "shortage",
    ]
    solution_keywords = [
        "solution", "response", "recommend", "lesson", "learn", "strategy",
        "mitigat", "vaccin", "treatment", "therap", "prevent", "contain",
        "surveillance", "WHO recommend", "guidance", "protocol", "guideline",
        "public health measure", "intervention", "risk communicat",
        "contact tracing", "quarantine", "isolation", "preparedness",
        "capacity building", "coordination", "mobiliz", "deploy",
    ]

    current_section = "crisis"

    for para in paragraphs:
        lower = para.lower()

        if any(h in lower for h in ["background", "context", "overview", "situation", "epidemiolog"]):
            current_section = "crisis"
            continue
        elif any(h in lower for h in ["impact", "effect", "consequence", "mortality", "morbidity", "burden"]):
            current_section = "impact"
            continue
        elif any(h in lower for h in ["response", "recommendation", "public health", "who advice", "conclusion", "guidance"]):
            current_section = "solution"
            continue

        crisis_score = sum(1 for k in crisis_keywords if k in lower)
        impact_score = sum(1 for k in impact_keywords if k in lower)
        solution_score = sum(1 for k in solution_keywords if k in lower)

        max_score = max(crisis_score, impact_score, solution_score)

        if max_score > 0:
            if crisis_score == max_score and current_section == "crisis":
                crisis_parts.append(para)
            elif impact_score == max_score:
                impact_parts.append(para)
            elif solution_score == max_score:
                solution_parts.append(para)
            else:
                if current_section == "crisis":
                    crisis_parts.append(para)
                elif current_section == "impact":
                    impact_parts.append(para)
                else:
                    solution_parts.append(para)
        else:
            if current_section == "crisis":
                crisis_parts.append(para)
            elif current_section == "impact":
                impact_parts.append(para)
            else:
                solution_parts.append(para)

    crisis = "\n".join(crisis_parts[:5])[:3000] or f"Health crisis described in: {title}"
    impact = "\n".join(impact_parts[:5])[:3000] or "Impact details not explicitly separated in the source report."
    solution = "\n".join(solution_parts[:5])[:3000] or "WHO response/recommendations not explicitly separated in the source report."

    return crisis, impact, solution


def detect_country(text: str) -> str:
    """Detect country mentions in text."""
    countries = [
        "Jordan", "Syria", "Lebanon", "Iraq", "Palestine", "Egypt", "Turkey",
        "Libya", "Yemen", "Somalia", "Sudan", "Ethiopia", "Kenya", "Mozambique",
        "Bangladesh", "India", "Nepal", "Pakistan", "Afghanistan", "Indonesia",
        "Philippines", "Japan", "China", "Haiti", "Chile", "Mexico", "Colombia",
        "Brazil", "Nigeria", "South Africa", "Australia", "New Zealand",
        "United States", "Italy", "Greece", "Morocco", "Tunisia", "Iran",
        "Democratic Republic of the Congo", "Uganda", "Tanzania", "Senegal",
        "Cameroon", "Mali", "Niger", "Chad", "Myanmar", "Thailand", "Vietnam",
        "Saudi Arabia", "Oman", "United Arab Emirates",
    ]
    found = [c for c in countries if c.lower() in text.lower()]
    return ", ".join(found[:3]) if found else "Global"


def detect_disaster_type(text: str) -> str:
    """Detect disaster/health event type from text."""
    types = {
        "Pandemic": ["pandemic", "covid", "sars-cov"],
        "Epidemic": ["epidemic", "outbreak"],
        "Cholera": ["cholera"],
        "Ebola": ["ebola", "marburg"],
        "Dengue": ["dengue"],
        "Mpox": ["mpox", "monkeypox"],
        "Avian Influenza": ["avian influenza", "bird flu", "h5n1", "h7n9"],
        "Yellow Fever": ["yellow fever"],
        "Measles": ["measles"],
        "Polio": ["polio", "poliovirus"],
        "Malaria": ["malaria"],
        "Plague": ["plague"],
        "Zika": ["zika"],
        "Earthquake": ["earthquake", "seismic"],
        "Flood": ["flood"],
        "Drought": ["drought"],
        "Cyclone/Hurricane": ["cyclone", "hurricane", "typhoon"],
        "Conflict": ["conflict", "war", "armed"],
    }
    lower = text.lower()
    found = [dtype for dtype, keywords in types.items() if any(k in lower for k in keywords)]
    return ", ".join(found[:2]) if found else "Health Emergency"


# ── Database insertion ───────────────────────────────────────────────
def insert_case_study(data: dict[str, Any]) -> bool:
    """Insert a case study into PostgreSQL."""
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
                        "who",
                        data.get("country", ""),
                        data.get("disaster_type", ""),
                        data.get("crisis", ""),
                        data.get("impact", ""),
                        data.get("solution", ""),
                        data.get("raw_text", ""),
                    ))
                    row = cur.fetchone()
                    return row is not None
        except Exception as e:
            print(f"  ❌ DB insert error: {e}")
            time.sleep(2)
    return False


# ── Main scraper ─────────────────────────────────────────────────────
def scrape_who() -> list[dict[str, Any]]:
    """Scrape WHO Disease Outbreak News and Emergency Situation Reports."""
    all_articles = []
    seen_urls: set[str] = set()

    # ── Phase 1: Disease Outbreak News ──────────────────────────────
    print("\n📋 Phase 1: Scraping WHO Disease Outbreak News...")
    for listing_url in WHO_DON_URLS:
        print(f"  🔍 Fetching listing: {listing_url}")
        soup = fetch_page(listing_url)
        if not soup:
            continue

        links = extract_don_links(soup)
        print(f"    📄 Found {len(links)} DON article links")

        for link in links[:150]:
            if link in seen_urls or len(all_articles) >= MAX_ARTICLES:
                continue
            seen_urls.add(link)

            time.sleep(DELAY_BETWEEN_REQUESTS)
            article_soup = fetch_page(link)
            if not article_soup:
                continue

            content = extract_article_content(article_soup, link)
            if content:
                all_articles.append(content)
                print(f"    ✅ {content['title'][:65]}")

    # ── Phase 2: Emergency Situation Reports ────────────────────────
    print("\n📋 Phase 2: Scraping WHO Emergency Situations...")
    for listing_url in WHO_EMERGENCY_URLS:
        print(f"  🔍 Fetching listing: {listing_url}")
        soup = fetch_page(listing_url)
        if not soup:
            continue

        links = extract_emergency_links(soup)
        print(f"    📄 Found {len(links)} emergency situation links")

        for link in links[:150]:
            if link in seen_urls or len(all_articles) >= MAX_ARTICLES:
                continue
            seen_urls.add(link)

            time.sleep(DELAY_BETWEEN_REQUESTS)
            article_soup = fetch_page(link)
            if not article_soup:
                continue

            content = extract_article_content(article_soup, link)
            if content:
                all_articles.append(content)
                print(f"    ✅ {content['title'][:65]}")

    return all_articles


def main():
    print("=" * 65)
    print("  AEGIS — WHO Disease Outbreak News & Emergencies Scraper")
    print("=" * 65)

    create_table()
    articles = scrape_who()
    print(f"\n  📊 Total articles collected: {len(articles)}\n")

    print("💾 Inserting into PostgreSQL...")
    inserted = 0
    skipped = 0
    for article in articles:
        if insert_case_study(article):
            print(f"  ✅ {article['title'][:70]}")
            inserted += 1
        else:
            skipped += 1

    print(f"\n{'=' * 65}")
    print(f"  ✅ Done! Inserted {inserted} articles, skipped {skipped} duplicates.")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
