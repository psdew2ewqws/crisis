class ScadaConnector:
    """Synthetic SCADA connector — pressure on PIPE-ZN-44."""

    source_id = "WAJ-SCADA"
    source_type = "scada"

    def discover_schema(self) -> dict:
        return {
            "fields": ["station_id", "metric", "value", "timestamp"],
            "types": ["str", "str", "float", "datetime"],
        }

    def poll(self) -> list[dict]:
        return [
            {
                "station_id": "PS-12",
                "metric": "inlet_pressure_bar",
                "value": 1.1,
                "timestamp": "2026-05-31T08:14:00Z",
            }
        ]

    def normalize(self, raw: dict) -> dict:
        return {
            "source": self.source_id,
            "observes": raw["station_id"],
            "metric": raw["metric"],
            "value": raw["value"],
            "baseline": 6.2,
            "severity_raw": "high" if raw["value"] < 2.0 else "low",
        }
