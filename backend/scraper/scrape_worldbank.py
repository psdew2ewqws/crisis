"""
World Bank Crisis Case Studies Scraper
=======================================
Scrapes real crisis case studies live from the World Bank Documents API.
Extracts (Crisis, Impact, Solution) from the abstracts,
and stores the structured data in PostgreSQL (voc360).

Usage:
    cd backend
    ./.venv/bin/python -m scraper.scrape_worldbank
"""
from __future__ import annotations

import json
import os
import hashlib
from typing import Any
import requests

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass

import psycopg

DSN = os.environ.get("VOC_DSN", "")

# ── SQL: Create table ────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ai_case_studies (
    id              SERIAL PRIMARY KEY,
    source_hash     VARCHAR(64) UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    source_url      TEXT,
    source_site     VARCHAR(50) DEFAULT 'worldbank',
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

def extract_crisis_impact_solution(text: str) -> tuple[str, str, str]:
    """Basic extraction logic to split an abstract into three parts."""
    sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 10]
    
    crisis_parts, impact_parts, solution_parts = [], [], []
    
    for s in sentences:
        s_lower = s.lower()
        if any(w in s_lower for w in ["lesson", "solution", "recommendation", "policy", "framework", "mitigate", "response", "project"]):
            solution_parts.append(s + ".")
        elif any(w in s_lower for w in ["impact", "damage", "loss", "killed", "destroyed", "affected", "economic", "cost"]):
            impact_parts.append(s + ".")
        else:
            crisis_parts.append(s + ".")
            
    crisis = " ".join(crisis_parts) or text[:300]
    impact = " ".join(impact_parts) or "Specific impact details not fully separated in the abstract."
    solution = " ".join(solution_parts) or "Specific solutions not fully separated in the abstract."
    
    return crisis[:3000], impact[:3000], solution[:3000]

def scrape_worldbank() -> list[dict[str, Any]]:
    print("🌐 Connecting to World Bank Live API...")
    url = "https://search.worldbank.org/api/v2/wds?format=json&qterm=disaster%20crisis%20lessons%20learned&fl=docna,url,txturl,abstracts&rows=20"
    
    resp = requests.get(url, timeout=15)
    data = resp.json()
    
    docs = data.get("documents", {})
    scraped = []
    
    for doc_id, doc in docs.items():
        if not isinstance(doc, dict):
            continue
            
        title = doc.get("display_title", "Unknown Title")
        abstract_dict = doc.get("abstracts", {})
        abstract = abstract_dict.get("cdata!", "") if abstract_dict else ""
        
        if not abstract or len(abstract) < 100:
            continue
            
        source_url = doc.get("url", f"https://documents.worldbank.org/en/publication/documents-reports/documentdetail/{doc_id}")
        
        crisis, impact, solution = extract_crisis_impact_solution(abstract)
        
        scraped.append({
            "title": title,
            "source_url": source_url,
            "country": "Global",
            "disaster_type": "Various",
            "crisis": crisis,
            "impact": impact,
            "solution": solution,
            "raw_text": abstract[:8000]
        })
        print(f"  ✅ Scraped live: {title[:60]}")
        
    return scraped

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
                        source_hash, data["title"], data["source_url"], "worldbank",
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
    print("  AEGIS — LIVE World Bank API Scraper")
    print("=" * 60)
    create_table()
    cases = scrape_worldbank()
    
    print("\n💾 Inserting into PostgreSQL...")
    inserted = 0
    for case in cases:
        if insert_case_study(case):
            inserted += 1
            
    print(f"\n✅ Done! Inserted {inserted} NEW live case studies from the World Bank.")

if __name__ == "__main__":
    main()
