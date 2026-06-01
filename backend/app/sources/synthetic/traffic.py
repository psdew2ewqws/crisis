class TrafficConnector:
    """Synthetic traffic congestion connector."""

    source_id = "Traffic"
    source_type = "traffic"

    def discover_schema(self) -> dict:
        return {
            "fields": ["junction_id", "congestion", "timestamp"],
            "types": ["str", "float", "datetime"],
        }

    def poll(self) -> list[dict]:
        return [
            {"junction_id": "JUNC-7", "congestion": 0.8,
             "timestamp": "2026-05-31T08:25:55Z"}
        ]

    def normalize(self, raw: dict) -> dict:
        return {
            "source": self.source_id,
            "observes": raw["junction_id"],
            "metric": "congestion",
            "value": raw["congestion"],
            "baseline": 0.3,
            "severity_raw": "low",
        }
