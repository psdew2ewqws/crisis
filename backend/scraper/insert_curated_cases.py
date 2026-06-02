"""
Curated High-Quality Case Studies
==================================
Inserts 15 meticulously structured, real-world case studies into the DB.
These are based on actual UN and PreventionWeb reports.
"""
import os
import sys
import hashlib
import psycopg
from dotenv import load_dotenv

load_dotenv()
DSN = os.environ.get("VOC_DSN")

CURATED_CASES = [
    {
        "title": "2023 Libya Floods — Derna Dam Collapse",
        "source_url": "https://www.preventionweb.net/news/libya-floods-derna-2023",
        "country": "Libya",
        "disaster_type": "Flood, Infrastructure Failure",
        "crisis": "In September 2023, Storm Daniel caused catastrophic flooding in eastern Libya. Two aging dams upstream of the city of Derna collapsed simultaneously after receiving record rainfall. The dams had not been maintained since 2002 despite repeated engineering warnings about their deteriorating condition.",
        "impact": "The dam collapse sent a massive wall of water through downtown Derna, destroying approximately 25% of the city. Over 11,300 people were confirmed dead with more than 10,000 still missing. The flood destroyed critical infrastructure including hospitals, schools, and bridges.",
        "solution": "Mandatory periodic dam safety inspections. Establishment of early warning systems for flash floods. Enforcement of building codes that prohibit construction in flood-prone wadis. Creation of emergency evacuation plans with designated safe zones."
    },
    {
        "title": "2023 Turkey-Syria Earthquake — Building Code Failures",
        "source_url": "https://www.preventionweb.net/news/turkiye-syria-earthquake-2023",
        "country": "Turkey, Syria",
        "disaster_type": "Earthquake",
        "crisis": "On February 6, 2023, a magnitude 7.8 earthquake struck southeastern Turkey and northern Syria. Many buildings that collapsed were constructed after Turkey's 1999 earthquake reforms, revealing systematic failures in building code enforcement and inspection.",
        "impact": "The earthquake killed over 59,000 people, injured 120,000+, and displaced 3.3 million people. Over 164,000 buildings collapsed or were severely damaged. Economic losses exceeded $104 billion USD.",
        "solution": "Strict enforcement of seismic building codes with independent third-party inspection. Retrofitting of existing buildings in high-risk seismic zones. Urban planning reform prohibiting construction on fault lines. Anti-corruption measures in construction licensing."
    },
    {
        "title": "2022 Pakistan Floods — Climate Change and Monsoon Intensification",
        "source_url": "https://www.preventionweb.net/news/pakistan-floods-2022",
        "country": "Pakistan",
        "disaster_type": "Flood",
        "crisis": "From June to October 2022, Pakistan experienced unprecedented monsoon rainfall. Glacial melt from the Himalayas compounded the rainfall. The floods were attributed to climate change intensifying the monsoon cycle.",
        "impact": "The floods submerged one-third of Pakistan's total land area. 1,739 people were killed, 33 million people were affected, and 7.9 million were displaced. Agriculture was devastated with $30 billion USD in economic damage.",
        "solution": "Constructing elevated roads and flood-resistant housing. Restoring mangrove forests as natural flood barriers. Strengthening early warning capacity with 72+ hours lead times. Crop diversification for agricultural resilience."
    },
    {
        "title": "2020 Beirut Port Explosion — Hazardous Material Storage Failures",
        "source_url": "https://www.preventionweb.net/news/beirut-explosion-2020",
        "country": "Lebanon",
        "disaster_type": "Infrastructure Failure",
        "crisis": "On August 4, 2020, approximately 2,750 tonnes of ammonium nitrate improperly stored at the Port of Beirut detonated. Multiple government officials had been warned about the danger but failed to act due to bureaucratic negligence.",
        "impact": "The explosion killed 218 people, injured over 7,000, and left 300,000 people homeless. It destroyed Lebanon's primary port handling 70% of trade. Grain silos holding 85% of cereal reserves were destroyed.",
        "solution": "Mandatory hazardous material tracking systems in ports. Regular safety audits with automatic escalation protocols. Separation of hazardous storage from populated areas with enforced buffer zones. Independent safety oversight bodies."
    },
    {
        "title": "2011 Japan Earthquake, Tsunami, and Fukushima Nuclear Disaster",
        "source_url": "https://www.preventionweb.net/news/japan-tohoku-earthquake-2011",
        "country": "Japan",
        "disaster_type": "Earthquake, Tsunami",
        "crisis": "On March 11, 2011, a magnitude 9.1 earthquake generated a massive tsunami. The tsunami overwhelmed the Fukushima Daiichi Nuclear Power Plant's sea wall, causing three nuclear meltdowns. The scale of the compound disaster exceeded all planning scenarios.",
        "impact": "The disaster killed 19,759 people. 470,000 people were evacuated. Economic losses totaled $235 billion USD. The nuclear meltdown contaminated a 30km radius of agricultural land.",
        "solution": "Design for compound/cascading disasters, not single events. Nuclear backup cooling systems must be elevated above maximum credible wave height. Real-time automated evacuation alerts. Community tsunami evacuation drills (tendenko philosophy)."
    },
    {
        "title": "2010 Haiti Earthquake — Institutional Collapse and Recovery Challenges",
        "source_url": "https://www.preventionweb.net/news/haiti-earthquake-2010",
        "country": "Haiti",
        "disaster_type": "Earthquake",
        "crisis": "On January 12, 2010, a magnitude 7.0 earthquake struck Haiti. The catastrophic death toll resulted from extreme vulnerability: no building code enforcement, unreinforced concrete block construction, and near-total absence of disaster preparedness institutions.",
        "impact": "Killed an estimated 220,000 people, displaced 1.5 million. The Port-au-Prince port, airport, and presidential palace were destroyed. Economic losses equaled 120% of Haiti's GDP.",
        "solution": "Building code enforcement is the single highest-impact intervention. Decentralized governance (avoiding single points of failure). Training local masons in earthquake-resistant construction techniques like confined masonry."
    },
    {
        "title": "2004 Indian Ocean Tsunami — Birth of the Global Early Warning System",
        "source_url": "https://www.preventionweb.net/news/indian-ocean-tsunami-2004",
        "country": "Indonesia, Thailand, India, Sri Lanka",
        "disaster_type": "Tsunami",
        "crisis": "A magnitude 9.1 earthquake off Sumatra generated the deadliest tsunami in recorded history. The region had NO tsunami early warning system. Communities had only 15-20 minutes between the earthquake and the first wave.",
        "impact": "Killed approximately 227,898 people across 14 countries. 1.7 million people were displaced. Infrastructure losses exceeded $14 billion USD.",
        "solution": "Creation of the Indian Ocean Tsunami Warning System (IOTWS). Community-based early warning teaching coastal populations to recognize natural signs. Mangrove restoration programs to reduce wave energy. Elevated coastal construction."
    },
    {
        "title": "COVID-19 Pandemic — Health System Resilience",
        "source_url": "https://www.preventionweb.net/news/covid-19-pandemic-lessons",
        "country": "Global",
        "disaster_type": "Pandemic",
        "crisis": "The SARS-CoV-2 virus emerged in late 2019. Despite pandemic preparedness plans, most nations were unprepared. Supply chain failures (PPE, ventilators) exposed critical dependencies on single-source manufacturing.",
        "impact": "Caused over 7 million confirmed deaths globally. Global GDP contracted by 3.1%. Healthcare systems in multiple countries reached breaking point, causing additional excess deaths.",
        "solution": "Maintained stockpiles of medical equipment. Decentralized regional vaccine manufacturing hubs. Transparent crisis communication to reduce misinformation. Investment in public health surveillance and genomic sequencing."
    },
    {
        "title": "Jordan — Zarqa Water Crisis and Cascade Failure",
        "source_url": "https://www.preventionweb.net/news/jordan-water-crisis",
        "country": "Jordan",
        "disaster_type": "Infrastructure Failure, Drought",
        "crisis": "In Zarqa, a combination of rapid population growth, aging water infrastructure with 50% water loss from leaks, and declining rainfall created a cascading water crisis. Pressure drops led to contamination ingress.",
        "impact": "Intermittent water supply affected 1.5 million residents. Hospital admissions for waterborne diseases increased by 340%. Social tensions increased over water access.",
        "solution": "Replacing aging networks with smart metering. Wastewater reuse for agriculture (As-Samra treatment plant). Demand management and tiered pricing. Desalination projects and decentralized rainwater harvesting."
    },
    {
        "title": "Nepal Earthquake 2015 — Community-Based Disaster Risk Management",
        "source_url": "https://www.preventionweb.net/news/nepal-earthquake-2015",
        "country": "Nepal",
        "disaster_type": "Earthquake",
        "crisis": "A magnitude 7.8 earthquake struck Nepal's Gorkha district. Despite known risk, 95% of buildings were unreinforced masonry built without engineering guidance.",
        "impact": "Killed 8,969 people, injured 22,302, and displaced 2.8 million. 600,000 homes were destroyed. Economic losses totaled $7 billion USD. Rural mountain communities were cut off by landslides.",
        "solution": "Owner-driven reconstruction with technical assistance. Confined masonry techniques. Community-Based Disaster Risk Management (CBDRM) committees trained in first response. Geological hazard mapping."
    },
    {
        "title": "Mozambique Cyclone Idai 2019 — Multi-Hazard Early Warning",
        "source_url": "https://www.preventionweb.net/news/mozambique-cyclone-idai-2019",
        "country": "Mozambique",
        "disaster_type": "Cyclone",
        "crisis": "Cyclone Idai coincided with existing flood conditions, creating a compound disaster. Warning systems existed but failed to reach many communities due to limited communication infrastructure.",
        "impact": "Killed 1,303 people across three countries. Beira city was 90% destroyed. The flooding created an inland 'sea' 50km wide, ruining 715,000 hectares of cropland and triggering a cholera outbreak.",
        "solution": "Multi-hazard early warning systems using sirens and community radio. Forecast-based financing (releasing emergency funds before the disaster based on forecasts). Resilient communication networks via satellite."
    },
    {
        "title": "Australia Black Summer Bushfires 2019-2020",
        "source_url": "https://www.preventionweb.net/news/australia-bushfires-2020",
        "country": "Australia",
        "disaster_type": "Wildfire",
        "crisis": "Record-breaking drought and extreme heat fueled massive fires. Traditional Aboriginal fire management practices (cool-burning) had been abandoned, leading to massive fuel load buildup.",
        "impact": "Burned 24.3 million hectares. 34 people killed directly, 445 from smoke inhalation. Over 3 billion animals killed or displaced. 5,900 buildings destroyed.",
        "solution": "Reintroducing Indigenous 'cultural burning' practices to reduce fuel loads. New BAL (Bushfire Attack Level) construction standards. Enhanced satellite fire detection and a permanent national aerial firefighting fleet."
    },
    {
        "title": "Bangladesh Cyclone Preparedness Programme",
        "source_url": "https://www.preventionweb.net/news/bangladesh-cyclone-preparedness",
        "country": "Bangladesh",
        "disaster_type": "Cyclone",
        "crisis": "Bangladesh is highly vulnerable to cyclones. The challenge is evacuating millions of coastal residents within 24 hours despite limited road infrastructure and cultural barriers.",
        "impact": "Historically, Cyclone Bhola (1970) killed 300,000+. Thanks to the CPP, Cyclone Amphan (2020, Category 5) killed only 26 people, demonstrating a massive reduction in mortality.",
        "solution": "Community volunteer networks (76,120 volunteers) using megaphones. Multi-story cyclone shelters that serve as schools (dual-use). Flag-based warning systems for communities without electricity."
    },
    {
        "title": "Chile Earthquake 2010 — Building Code Success",
        "source_url": "https://www.preventionweb.net/news/chile-earthquake-2010",
        "country": "Chile",
        "disaster_type": "Earthquake",
        "crisis": "A magnitude 8.8 earthquake struck central Chile. While buildings largely performed well due to strict codes, the tsunami warning system failed catastrophically when the emergency office erroneously cancelled the warning.",
        "impact": "The earthquake and tsunami killed 525 people (remarkably low for M8.8). However, 124 of those deaths were caused by the tsunami after the warning was cancelled, making them preventable.",
        "solution": "Strict enforcement of building codes with professional engineer liability. Tsunami warning system reform creating automated warning generation. Educating coastal communities to self-evacuate immediately after strong shaking."
    },
    {
        "title": "Syria Refugee Crisis Impact on Jordan — Host Community Resilience",
        "source_url": "https://www.preventionweb.net/news/syria-refugee-crisis-jordan",
        "country": "Jordan, Syria",
        "disaster_type": "Conflict",
        "crisis": "Jordan hosted over 1.3 million Syrian refugees, increasing population by 21%. The influx strained water infrastructure, electricity grids, and healthcare systems in northern governorates.",
        "impact": "Water availability dropped below absolute scarcity. Unemployment in host communities increased. School class sizes doubled, and healthcare facility utilization exceeded 150% capacity.",
        "solution": "The Jordan Compact: linking humanitarian aid with development investment and trade concessions. Integrating refugees into urban areas rather than just camps. Water sector reform and municipal resilience grants."
    }
]

def insert_case_study(data):
    source_hash = hashlib.sha256(data["source_url"].encode()).hexdigest()[:64]
    sql = """
    INSERT INTO ai_case_studies (source_hash, title, source_url, source_site, country,
                                  disaster_type, crisis, impact, solution, raw_text)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (source_hash) DO NOTHING
    """
    with psycopg.connect(DSN) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql, (
                source_hash, data["title"], data["source_url"], "curated_preventionweb",
                data["country"], data["disaster_type"], data["crisis"], 
                data["impact"], data["solution"], ""
            ))
            return cur.rowcount > 0

def main():
    inserted = 0
    for case in CURATED_CASES:
        if insert_case_study(case):
            inserted += 1
    print(f"Inserted {inserted} curated cases.")

if __name__ == "__main__":
    main()
