"""Water Domain Pack — Zarqa water-pipe cascade scenario."""
import json
import os
from app.packs.base import DomainPack


class WaterPack(DomainPack):
    domain_key = "water"
    name = "Water Infrastructure"

    def get_ontology(self) -> dict:
        return {
            "node_types": ["pipe", "pump", "reservoir", "water_distribution",
                          "hospital", "distribution_point", "road", "population", "psap"],
            "edge_types": ["feeds", "supplies", "provides", "serves",
                          "depends_on", "activated_by", "impacted_by", "load_from"],
        }

    def get_propagation_rules(self) -> list[dict]:
        return [
            {"rel": "feeds", "weight": 0.95, "lag_s": 0},
            {"rel": "supplies", "weight": 0.90, "lag_s": 300},
            {"rel": "provides", "weight": 1.00, "lag_s": 300},
            {"rel": "serves", "weight": 1.00, "lag_s": 0},
            {"rel": "depends_on", "weight": 0.60, "lag_s": 1800},
            {"rel": "activated_by", "weight": 0.70, "lag_s": 1500},
            {"rel": "impacted_by", "weight": 0.40, "lag_s": 2400},
            {"rel": "load_from", "weight": 0.50, "lag_s": 2400},
        ]

    def get_intervention_library(self) -> list[dict]:
        return [
            {"id": "INT-A", "title": "Isolate ZN-44 + bypass via ZN-12 + 4 tankers",
             "actions": ["close_valve_V441", "open_bypass_V128", "dispatch_4_tankers"],
             "cost": "medium", "eta_min": 35, "risk_reduction": "high"},
            {"id": "INT-B", "title": "Isolate only",
             "actions": ["close_valve_V441"],
             "cost": "low", "eta_min": 15, "risk_reduction": "medium"},
            {"id": "INT-C", "title": "Tankers only",
             "actions": ["dispatch_6_tankers"],
             "cost": "high", "eta_min": 50, "risk_reduction": "low"},
        ]

    def get_seed_data(self) -> dict:
        seed_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "seeds", "zarqa.json"
        )
        return json.load(open(seed_path))
