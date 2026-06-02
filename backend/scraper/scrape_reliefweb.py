"""
ReliefWeb Scraper
==================
Scrapes humanitarian crisis reports from ReliefWeb (managed by UN OCHA).
ReliefWeb's API now requires pre-approved appnames, so we scrape
the website directly.

Extracts (Crisis, Impact, Solution) from each report,
and stores the structured data in PostgreSQL (voc360).

Usage:
    cd backend
    ./.venv/bin/python -m scraper.scrape_reliefweb
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

RW_BASE = "https://reliefweb.int"

# ReliefWeb search URLs — updates section with various crisis queries
RW_SEARCH_URLS = [
    f"{RW_BASE}/updates?search=earthquake+disaster+response&view=reports",
    f"{RW_BASE}/updates?search=flood+crisis+humanitarian&view=reports",
    f"{RW_BASE}/updates?search=drought+famine+food+crisis&view=reports",
    f"{RW_BASE}/updates?search=cyclone+hurricane+typhoon+emergency&view=reports",
    f"{RW_BASE}/updates?search=conflict+refugee+displacement&view=reports",
    f"{RW_BASE}/updates?search=Jordan+crisis+humanitarian&view=reports",
    f"{RW_BASE}/updates?search=disaster+risk+reduction+resilience&view=reports",
    f"{RW_BASE}/updates?search=pandemic+health+emergency&view=reports",
]

MAX_ARTICLES = 500
DELAY_BETWEEN_REQUESTS = 1  # seconds

# ── SQL ──────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ai_case_studies (
    id              SERIAL PRIMARY KEY,
    source_hash     VARCHAR(64) UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    source_url      TEXT,
    source_site     VARCHAR(50) DEFAULT 'reliefweb',
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
    """Fetch a URL and return BeautifulSoup object."""
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


def extract_report_links(soup: BeautifulSoup) -> list[str]:
    """Extract report article links from a ReliefWeb search results page."""
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/report/" in href:
            full_url = href if href.startswith("http") else RW_BASE + href
            if full_url not in links and "reliefweb.int" in full_url:
                links.append(full_url)
    return links


def extract_article_content(soup: BeautifulSoup, url: str) -> dict[str, Any] | None:
    """Extract structured content from a ReliefWeb report page."""
    # Title
    title_tag = soup.find("h1") or soup.find("title")
    if not title_tag:
        return None
    title = title_tag.get_text(strip=True)
    if len(title) < 10:
        return None

    # Clean title
    title = re.sub(r'\s*[-–|]\s*ReliefWeb$', '', title).strip()

    # Main body text
    body_text = ""
    for selector in [
        "article", ".rw-article__content", ".rw-report__content",
        ".field--name-body", ".node__content", "main",
    ]:
        if "." in selector:
            container = soup.select_one(selector)
        else:
            container = soup.find(selector)
        if container:
            body_text = container.get_text(separator="\n", strip=True)
            break

    if not body_text or len(body_text) < 150:
        paragraphs = soup.find_all("p")
        body_text = "\n".join(
            p.get_text(strip=True) for p in paragraphs
            if len(p.get_text(strip=True)) > 30
        )

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
    """Extract crisis, impact, and solution using keyword heuristics."""
    paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]

    crisis_parts = []
    impact_parts = []
    solution_parts = []

    crisis_keywords = [
        "crisis", "disaster", "earthquake", "flood", "drought", "pandemic",
        "outbreak", "conflict", "emergency", "hazard", "storm", "cyclone",
        "tsunami", "landslide", "volcano", "wildfire", "famine", "collapse",
        "threat", "risk", "vulnerability", "struck", "hit", "devastat",
        "situation", "escalat", "deteriorat", "alert",
    ]
    impact_keywords = [
        "impact", "affect", "damage", "loss", "casualt", "displac", "injur",
        "death", "destruction", "econom", "cost", "billion", "million",
        "homeless", "refugee", "livelihood", "infrastructure", "suffer",
        "consequence", "result", "toll", "victim", "destroyed",
        "food insecurity", "malnutrition", "mortality",
    ]
    solution_keywords = [
        "solution", "response", "recommend", "lesson", "learn", "strategy",
        "mitigat", "adapt", "resilien", "prevent", "reduc", "recover",
        "reconstruct", "rebuild", "policy", "framework", "plan", "interven",
        "measure", "action", "implement", "best practice", "approach",
        "early warning", "preparedness", "capacity building", "governance",
        "program", "initiative", "reform", "coordination", "mobiliz",
        "humanitarian aid", "relief", "assistance", "funding",
    ]

    current_section = "crisis"

    for para in paragraphs:
        lower = para.lower()

        if any(h in lower for h in ["background", "context", "overview", "introduction", "the crisis", "situation overview"]):
            current_section = "crisis"
            continue
        elif any(h in lower for h in ["impact", "effect", "consequence", "damage", "needs", "humanitarian needs"]):
            current_section = "impact"
            continue
        elif any(h in lower for h in ["solution", "response", "recommendation", "lesson", "way forward", "conclusion", "coordination"]):
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

    crisis = "\n".join(crisis_parts[:5])[:3000] or f"Crisis described in: {title}"
    impact = "\n".join(impact_parts[:5])[:3000] or "Impact details not explicitly separated in the source report."
    solution = "\n".join(solution_parts[:5])[:3000] or "Response/solution details not explicitly separated in the source report."

    return crisis, impact, solution


def detect_country(text: str) -> str:
    """Detect country mentions in text."""
    countries = [
        "Jordan", "Syria", "Lebanon", "Iraq", "Palestine", "Egypt", "Turkey",
        "Libya", "Yemen", "Somalia", "Sudan", "South Sudan", "Ethiopia",
        "Kenya", "Mozambique", "Bangladesh", "India", "Nepal", "Pakistan",
        "Afghanistan", "Indonesia", "Philippines", "Japan", "China", "Haiti",
        "Chile", "Mexico", "Colombia", "Brazil", "Nigeria", "South Africa",
        "Australia", "New Zealand", "United States", "Italy", "Greece",
        "Morocco", "Tunisia", "Iran", "Myanmar", "Ukraine",
        "Democratic Republic of the Congo",
    ]
    found = [c for c in countries if c.lower() in text.lower()]
    return ", ".join(found[:3]) if found else "Global"


def detect_disaster_type(text: str) -> str:
    """Detect disaster type from text."""
    types = {
        "Earthquake": ["earthquake", "seismic"],
        "Flood": ["flood", "flooding", "flash flood"],
        "Drought": ["drought", "water scarcity"],
        "Cyclone/Hurricane": ["cyclone", "hurricane", "typhoon"],
        "Tsunami": ["tsunami"],
        "Landslide": ["landslide", "mudslide"],
        "Wildfire": ["wildfire", "forest fire"],
        "Pandemic": ["pandemic", "epidemic", "outbreak", "covid"],
        "Conflict": ["conflict", "war", "armed", "refugee"],
        "Volcanic": ["volcano", "volcanic"],
        "Famine": ["famine", "food crisis", "hunger"],
    }
    lower = text.lower()
    found = [dtype for dtype, keywords in types.items() if any(k in lower for k in keywords)]
    return ", ".join(found[:2]) if found else "Multi-hazard"


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
                        "reliefweb",
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


# ── Main ─────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  AEGIS — ReliefWeb Live Reports Scraper")
    print("=" * 65)

    create_table()

    all_articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for search_url in RW_SEARCH_URLS:
        print(f"\n  🔍 Fetching: {search_url[:80]}...")
        soup = fetch_page(search_url)
        if not soup:
            continue

        links = extract_report_links(soup)
        print(f"    📄 Found {len(links)} report links")

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

    print(f"\n  📊 Total unique reports collected: {len(all_articles)}\n")

    print("💾 Inserting into PostgreSQL...")
    inserted = 0
    skipped = 0
    for article in all_articles:
        if insert_case_study(article):
            print(f"  ✅ {article['title'][:70]}")
            inserted += 1
        else:
            skipped += 1

    print(f"\n{'=' * 65}")
    print(f"  ✅ Done! Inserted {inserted} reports, skipped {skipped} duplicates.")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
