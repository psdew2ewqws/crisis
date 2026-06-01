class HospitalConnector:
    """Synthetic hospital ED occupancy connector."""

    source_id = "MoH"
    source_type = "hospital"

    def discover_schema(self) -> dict:
        return {
            "fields": ["hospital_id", "metric", "value", "timestamp"],
            "types": ["str", "str", "float", "datetime"],
        }

    def poll(self) -> list[dict]:
        return [
            {"hospital_id": "HOSP-ZN-1", "metric": "ed_occupancy", "value": 0.94,
             "timestamp": "2026-05-31T08:22:00Z"}
        ]

    def normalize(self, raw: dict) -> dict:
        return {
            "source": self.source_id,
            "observes": raw["hospital_id"],
            "metric": raw["metric"],
            "value": raw["value"],
            "baseline": 0.70,
            "severity_raw": "med" if raw["value"] > 0.85 else "low",
        }
