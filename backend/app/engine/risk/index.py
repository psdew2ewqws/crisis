def national_index(risks: dict[str, float]) -> dict:
    """Aggregate node risks to national + by_location (§5.6)."""
    if not risks:
        return {"national": 0.0, "by_node": {}, "top_contributors": []}
    values = list(risks.values())
    national = round(max(values) * 100, 1)  # scale to 0-100
    sorted_risks = sorted(risks.items(), key=lambda x: -x[1])
    return {
        "national": min(national, 100.0),
        "by_node": risks,
        "top_contributors": [
            {"node_id": nid, "risk": round(r * 100, 1)}
            for nid, r in sorted_risks[:5]
        ],
    }
