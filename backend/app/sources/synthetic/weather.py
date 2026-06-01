class WeatherConnector:
    """Synthetic weather connector — the advanced external signal source."""

    source_id = "Weather"
    source_type = "weather"

    def discover_schema(self) -> dict:
        return {
            "fields": ["region", "metric", "value", "timestamp"],
            "types": ["str", "str", "float", "datetime"],
        }

    def poll(self) -> list[dict]:
        return [
            {"region": "JO-AZ-N", "metric": "temperature_c", "value": 42.0,
             "timestamp": "2026-05-31T12:00:00Z"},
            {"region": "JO-AZ-N", "metric": "humidity_pct", "value": 12.0,
             "timestamp": "2026-05-31T12:00:00Z"},
        ]

    def normalize(self, raw: dict) -> dict:
        return {
            "source": self.source_id,
            "observes": "POP-ZN",  # weather affects the population
            "metric": raw["metric"],
            "value": raw["value"],
            "baseline": 35.0 if raw["metric"] == "temperature_c" else 40.0,
            "severity_raw": "low",
        }
