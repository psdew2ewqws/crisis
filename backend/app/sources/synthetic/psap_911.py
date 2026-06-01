class Psap911Connector:
    """Synthetic 911 call-volume surge connector."""

    source_id = "PSAP-911"
    source_type = "psap"

    def discover_schema(self) -> dict:
        return {
            "fields": ["zone", "call_count", "timestamp"],
            "types": ["str", "int", "datetime"],
        }

    def poll(self) -> list[dict]:
        return [
            {"zone": "COMMS-911", "call_count": 420, "timestamp": "2026-05-31T08:29:00Z"}
        ]

    def normalize(self, raw: dict) -> dict:
        return {
            "source": self.source_id,
            "observes": raw["zone"],
            "metric": "call_volume",
            "value": raw["call_count"],
            "baseline": 100,
            "severity_raw": "high" if raw["call_count"] > 250 else "low",
        }
