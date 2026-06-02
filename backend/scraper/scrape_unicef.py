"""
UNICEF Scraper — via ReliefWeb (UNICEF-sourced reports)
========================================================
UNICEF's own website blocks scraping (HTTP 403).
This scraper fetches UNICEF humanitarian reports from ReliefWeb,
which indexes all UNICEF publications and is scraping-friendly.

Usage:
    cd backend
    ./.venv/bin/python -m scraper.scrape_unicef
"""
from __future__ import annotations

import os
import sys
import hashlib
import time
import re
import requests
from bs4 import BeautifulSoup
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
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

RW_BASE = "https://reliefweb.int"

# ReliefWeb search URLs filtering for UNICEF-sourced reports
UNICEF_SEARCH_URLS = [
    f"{RW_BASE}/updates?search=UNICEF+humanitarian+children+emergency&view=reports",
    f"{RW_BASE}/updates?search=UNICEF+situation+report+children&view=reports",
    f"{RW_BASE}/updates?search=UNICEF+flash+appeal+children&view=reports",
    f"{RW_BASE}/updates?search=humanitarian+action+children+UNICEF&view=reports",
    f"{RW_BASE}/updates?search=UNICEF+child+protection+emergency&view=reports",
]

MAX_ARTICLES = 120
DELAY = 1.5


# ── Helpers ──────────────────────────────────────────────────────────
def fetch_page(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
        print(f"  ⚠️  HTTP {r.status_code} — {url[:70]}")
        return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def extract_report_links(soup: BeautifulSoup) -> list[str]:
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/report/" in href:
            full = href if href.startswith("http") else RW_BASE + href
            if full not in links and "reliefweb.int" in full:
                links.append(full)
    return links


def detect_country(text: str) -> str:
    countries = [
        "Jordan", "Syria", "Lebanon", "Iraq", "Palestine", "Egypt", "Turkey",
        "Libya", "Yemen", "Somalia", "Sudan", "South Sudan", "Ethiopia",
        "Kenya", "Mozambique", "Bangladesh", "India", "Nepal", "Pakistan",
        "Afghanistan", "Indonesia", "Philippines", "Haiti", "Colombia",
        "Nigeria", "Democratic Republic of the Congo", "Myanmar", "Ukraine",
        "Central African Republic", "Mali", "Niger", "Chad", "Venezuela",
        "South Africa", "Zimbabwe", "Malawi", "Tanzania", "Uganda",
    ]
    found = [c for c in countries if c.lower() in text.lower()]
    return ", ".join(found[:3]) if found else "Global"


def detect_disaster_type(text: str) -> str:
    types = {
        "Earthquake": ["earthquake", "seismic"],
        "Flood": ["flood", "flooding"],
        "Drought": ["drought", "water scarcity", "famine", "hunger"],
        "Cyclone/Hurricane": ["cyclone", "hurricane", "typhoon"],
        "Conflict": ["conflict", "war", "armed", "violence", "displacement"],
        "Pandemic": ["pandemic", "epidemic", "outbreak", "covid", "cholera"],
        "Refugee Crisis": ["refugee", "asylum", "migration"],
    }
    lower = text.lower()
    found = [dtype for dtype, kws in types.items() if any(k in lower for k in kws)]
    return ", ".join(found[:2]) if found else "Complex Emergency"


def extract_crisis_impact_solution(title: str, text: str) -> tuple[str, str, str]:
    paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]

    crisis_kws = [
        "crisis", "emergency", "disaster", "conflict", "outbreak", "flood",
        "drought", "earthquake", "cyclone", "displacement", "violence",
        "insecurity", "deteriorat", "escalat",
    ]
    impact_kws = [
        "children", "child", "affect", "displace", "malnutrition", "death",
        "casualt", "million", "thousand", "need", "vulnerable", "homeless",
        "school", "health", "water", "food", "protection",
    ]
    solution_kws = [
        "response", "unicef", "provide", "supply", "deploy", "funding",
        "appeal", "program", "service", "support", "assist", "vaccin",
        "distribute", "rehabilitat", "protect", "train", "capacit",
    ]

    crisis_parts, impact_parts, solution_parts = [], [], []
    current = "crisis"

    for para in paragraphs:
        lower = para.lower()
        if any(h in lower for h in ["background", "context", "overview", "situation", "the crisis"]):
            current = "crisis"; continue
        elif any(h in lower for h in ["impact", "children affected", "needs", "consequence"]):
            current = "impact"; continue
        elif any(h in lower for h in ["response", "unicef response", "funding", "action taken"]):
            current = "solution"; continue

        cs = sum(1 for k in crisis_kws if k in lower)
        im = sum(1 for k in impact_kws if k in lower)
        so = sum(1 for k in solution_kws if k in lower)
        mx = max(cs, im, so)

        if mx > 0:
            if cs == mx and current == "crisis":
                crisis_parts.append(para)
            elif im == mx:
                impact_parts.append(para)
            elif so == mx:
                solution_parts.append(para)
            else:
                {"crisis": crisis_parts, "impact": impact_parts, "solution": solution_parts}[current].append(para)
        else:
            {"crisis": crisis_parts, "impact": impact_parts, "solution": solution_parts}[current].append(para)

    crisis = "\n".join(crisis_parts[:5])[:3000] or f"UNICEF humanitarian emergency: {title}"
    impact = "\n".join(impact_parts[:5])[:3000] or "Impact on children and vulnerable populations described in report."
    solution = "\n".join(solution_parts[:5])[:3000] or "UNICEF response: WASH, child protection, education, and nutrition services."
    return crisis, impact, solution


def extract_article_content(soup: BeautifulSoup, url: str) -> dict[str, Any] | None:
    title_tag = soup.find("h1") or soup.find("title")
    if not title_tag:
        return None
    title = title_tag.get_text(strip=True)
    title = re.sub(r'\s*[-–|]\s*(ReliefWeb|UNICEF)$', '', title).strip()
    if len(title) < 10:
        return None

    body_text = ""
    for sel in ["article", ".rw-article__content", ".field--name-body", ".node__content", "main"]:
        container = soup.select_one(sel) if "." in sel else soup.find(sel)
        if container:
            body_text = container.get_text(separator="\n", strip=True)
            break

    if not body_text or len(body_text) < 150:
        body_text = "\n".join(
            p.get_text(strip=True) for p in soup.find_all("p")
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


def insert_case_study(data: dict[str, Any]) -> bool:
    source_hash = hashlib.sha256(data["source_url"].encode()).hexdigest()[:64]
    sql = """
    INSERT INTO ai_case_studies (source_hash, title, source_url, source_site, country,
                                  disaster_type, crisis, impact, solution, raw_text)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (source_hash) DO NOTHING
    RETURNING id;
    """
    for _ in range(3):
        try:
            with psycopg.connect(DSN, connect_timeout=30) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(sql, (
                        source_hash, data["title"], data["source_url"], "unicef",
                        data.get("country", ""), data.get("disaster_type", "Complex Emergency"),
                        data.get("crisis", ""), data.get("impact", ""),
                        data.get("solution", ""), data.get("raw_text", ""),
                    ))
                    return cur.fetchone() is not None
        except Exception as e:
            print(f"  ❌ DB insert error: {e}")
            time.sleep(2)
    return False


# ── Main ──────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  AEGIS — UNICEF Reports Scraper (via ReliefWeb)")
    print("=" * 65)

    all_articles: list[dict] = []
    seen_urls: set[str] = set()

    for search_url in UNICEF_SEARCH_URLS:
        if len(all_articles) >= MAX_ARTICLES:
            break
        print(f"\n🔍 Fetching: {search_url[:80]}...")
        soup = fetch_page(search_url)
        if not soup:
            continue

        links = extract_report_links(soup)
        print(f"  📄 Found {len(links)} report links")

        for link in links[:30]:
            if link in seen_urls or len(all_articles) >= MAX_ARTICLES:
                continue
            seen_urls.add(link)
            time.sleep(DELAY)

            article_soup = fetch_page(link)
            if not article_soup:
                continue

            content = extract_article_content(article_soup, link)
            if content:
                all_articles.append(content)
                print(f"  ✅ {content['title'][:65]}")

    print(f"\n  📊 Total UNICEF reports collected: {len(all_articles)}\n")
    print("💾 Inserting into PostgreSQL...")

    inserted = skipped = 0
    for article in all_articles:
        if insert_case_study(article):
            inserted += 1
        else:
            skipped += 1

    print(f"\n{'=' * 65}")
    print(f"  ✅ Done! Inserted {inserted} records, skipped {skipped} duplicates.")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
