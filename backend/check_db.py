import os, psycopg
from dotenv import load_dotenv
load_dotenv(".env")
dsn = os.environ.get("VOC_DSN", "")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        # Total count
        cur.execute("SELECT COUNT(*) FROM ai_case_studies;")
        total = cur.fetchone()[0]
        
        # Count by source
        cur.execute("SELECT source_site, COUNT(*) FROM ai_case_studies GROUP BY source_site ORDER BY COUNT(*) DESC;")
        sources = cur.fetchall()
        
        # Count by disaster type
        cur.execute("SELECT COALESCE(NULLIF(disaster_type, ''), 'Unspecified'), COUNT(*) FROM ai_case_studies GROUP BY 1 ORDER BY 2 DESC LIMIT 5;")
        types = cur.fetchall()
        
        print(f"Total Cases: {total}")
        print("\nBy Source:")
        for s in sources: print(f" - {s[0]}: {s[1]}")
        print("\nBy Disaster Type (Top 5):")
        for t in types: print(f" - {t[0]}: {t[1]}")
