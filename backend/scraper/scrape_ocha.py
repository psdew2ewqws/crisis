"""
UN OCHA (Office for the Coordination of Humanitarian Affairs) Scraper
======================================================================
Scrapes humanitarian reports and disaster data from UN OCHA sources:
  1. ReliefWeb website (filtered for OCHA-sourced reports)
  2. UNOCHA.org situation reports and flash updates

Extracts (Crisis, Impact, Solution) from each report,
and stores the structured data in PostgreSQL (voc360).

Usage:
    cd backend
    ./.venv/bin/python -m scraper.scrape_ocha
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

# ReliefWeb OCHA-sourced reports
RW_BASE = "https://reliefweb.int"
RW_OCHA_URLS = [
    f"{RW_BASE}/updates?search=OCHA+situation+report&view=reports",
    f"{RW_BASE}/updates?search=OCHA+humanitarian+coordination&view=reports",
    f"{RW_BASE}/updates?search=OCHA+flash+appeal+emergency&view=reports",
    f"{RW_BASE}/updates?search=humanitarian+needs+overview&view=reports",
    f"{RW_BASE}/updates?search=CERF+allocation+response&view=reports",
    f"{RW_BASE}/updates?search=inter-agency+coordination+humanitarian&view=reports",
]

# UNOCHA.org direct pages
OCHA_BASE = "https://www.unocha.org"
OCHA_PAGES = [
    f"{OCHA_BASE}/where-we-work",
    f"{OCHA_BASE}/our-work/coordination",
]

MAX_ARTICLES = 500
DELAY_BETWEEN_REQUESTS = 1

# ── SQL ──────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ai_case_studies (
    id              SERIAL PRIMARY KEY,
    source_hash     VARCHAR(64) UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    source_url      TEXT,
    source_site     VARCHAR(50) DEFAULT 'ocha',
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


def extract_rw_report_links(soup: BeautifulSoup) -> list[str]:
    """Extract report links from ReliefWeb search results."""
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/report/" in href:
            full_url = href if href.startswith("http") else RW_BASE + href
            if full_url not in links and "reliefweb.int" in full_url:
                links.append(full_url)
    return links


def extract_ocha_links(soup: BeautifulSoup) -> list[str]:
    """Extract article/page links from UNOCHA.org pages."""
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if any(p in href for p in [
            "/story/", "/news/", "/press-release/", "/situation-report/",
            "/where-we-work/", "/flash-update/",
        ]):
            full_url = href if href.startswith("http") else OCHA_BASE + href
            if full_url not in links and ("unocha.org" in full_url or "reliefweb.int" in full_url):
                links.append(full_url)
    return links


def extract_article_content(soup: BeautifulSoup, url: str) -> dict[str, Any] | None:
    """Extract structured content from a report page."""
    title_tag = soup.find("h1") or soup.find("title")
    if not title_tag:
        return None
    title = title_tag.get_text(strip=True)
    if len(title) < 10:
        return None

    # Clean common suffixes
    title = re.sub(r'\s*[-–|]\s*(ReliefWeb|OCHA|UN OCHA)$', '', title).strip()

    # Main body text
    body_text = ""
    for selector in [
        "article", ".rw-article__content", ".rw-report__content",
        ".field--name-body", ".node__content", ".content-block", "main",
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
    """Extract crisis, impact, and solution — tailored for OCHA reports."""
    paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]

    crisis_parts = []
    impact_parts = []
    solution_parts = []

    crisis_keywords = [
        "crisis", "disaster", "earthquake", "flood", "drought", "pandemic",
        "outbreak", "conflict", "emergency", "hazard", "storm", "cyclone",
        "escalat", "deteriorat", "situation", "alert", "threat",
        "hostilities", "violence", "displacement", "insecurity",
    ]
    impact_keywords = [
        "impact", "affect", "damage", "loss", "casualt", "displac", "injur",
        "death", "destruction", "econom", "cost", "billion", "million",
        "people in need", "food insecurity", "malnutrition", "mortality",
        "homeless", "refugee", "livelihood", "infrastructure", "suffer",
        "humanitarian needs", "vulnerable", "access",
    ]
    solution_keywords = [
        "response", "coordination", "humanitarian aid", "relief",
        "assistance", "funding", "appeal", "CERF", "cluster",
        "inter-agency", "mobiliz", "deploy", "operation",
        "recommend", "lesson", "strategy", "framework", "plan",
        "preparedness", "early warning", "capacity building",
        "resilience", "recovery", "reconstruction", "intervention",
        "protection", "shelter", "WASH", "food distribution",
    ]

    current_section = "crisis"

    for para in paragraphs:
        lower = para.lower()

        if any(h in lower for h in [
            "background", "context", "overview", "introduction",
            "situation overview", "the crisis", "key developments",
        ]):
            current_section = "crisis"
            continue
        elif any(h in lower for h in [
            "impact", "humanitarian needs", "effect", "consequence",
            "people in need", "displacement", "damage assessment",
        ]):
            current_section = "impact"
            continue
        elif any(h in lower for h in [
            "response", "coordination", "funding", "recommendation",
            "cluster", "operational", "way forward", "humanitarian action",
        ]):
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

    crisis = "\n".join(crisis_parts[:5])[:3000] or f"Humanitarian crisis described in: {title}"
    impact = "\n".join(impact_parts[:5])[:3000] or "Impact/needs details not explicitly separated in the source report."
    solution = "\n".join(solution_parts[:5])[:3000] or "Response/coordination details not explicitly separated in the source report."

    return crisis, impact, solution


def detect_country(text: str) -> str:
    """Detect country mentions."""
    countries = [
        "Jordan", "Syria", "Lebanon", "Iraq", "Palestine", "Egypt", "Turkey",
        "Libya", "Yemen", "Somalia", "Sudan", "South Sudan", "Ethiopia",
        "Kenya", "Mozambique", "Bangladesh", "India", "Nepal", "Pakistan",
        "Afghanistan", "Indonesia", "Philippines", "Haiti", "Colombia",
        "Nigeria", "Democratic Republic of the Congo", "Myanmar", "Ukraine",
        "Central African Republic", "Mali", "Niger", "Chad", "Burkina Faso",
    ]
    found = [c for c in countries if c.lower() in text.lower()]
    return ", ".join(found[:3]) if found else "Global"


def detect_disaster_type(text: str) -> str:
    """Detect disaster type."""
    types = {
        "Earthquake": ["earthquake", "seismic"],
        "Flood": ["flood", "flooding"],
        "Drought": ["drought", "water scarcity"],
        "Cyclone/Hurricane": ["cyclone", "hurricane", "typhoon"],
        "Conflict": ["conflict", "war", "armed", "hostilities"],
        "Pandemic": ["pandemic", "epidemic", "outbreak"],
        "Famine": ["famine", "food crisis", "hunger"],
        "Displacement": ["refugee", "displacement", "IDP"],
    }
    lower = text.lower()
    found = [dtype for dtype, keywords in types.items() if any(k in lower for k in keywords)]
    return ", ".join(found[:2]) if found else "Humanitarian Crisis"


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
                        "ocha",
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
    print("  AEGIS — UN OCHA Humanitarian Reports Scraper")
    print("=" * 65)

    create_table()

    all_articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    # ── Phase 1: OCHA reports from ReliefWeb ────────────────────────
    print("\n📋 Phase 1: Scraping OCHA reports from ReliefWeb...")
    for search_url in RW_OCHA_URLS:
        print(f"\n  🔍 Fetching: {search_url[:80]}...")
        soup = fetch_page(search_url)
        if not soup:
            continue

        links = extract_rw_report_links(soup)
        print(f"    📄 Found {len(links)} report links")

        for link in links[:100]:
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

    # ── Phase 2: UNOCHA.org direct pages ────────────────────────────
    print(f"\n📋 Phase 2: Scraping UNOCHA.org...")
    for page_url in OCHA_PAGES:
        print(f"\n  🔍 Fetching: {page_url}")
        soup = fetch_page(page_url)
        if not soup:
            continue

        links = extract_ocha_links(soup)
        print(f"    📄 Found {len(links)} OCHA article links")

        for link in links[:100]:
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

    # ── Insert all ──────────────────────────────────────────────────
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
    print(f"  ✅ Done! Inserted {inserted} records, skipped {skipped} duplicates.")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
