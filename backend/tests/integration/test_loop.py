"""Integration tests — full workflow loop matching MVP acceptance criteria."""
from httpx import AsyncClient

INCIDENT_ID = "INC-ZARQA-2026-05"


class TestFullCrisisLoop:
    """End-to-end: signal → root cause → risk → solution → simulation → decision."""

    async def test_mvp_acceptance_loop(self, client: AsyncClient):
        """Acceptance: root_cause=PIPE-ZN-44, risk drops, decision authorized."""

        # Step 1: Verify root cause
        r = await client.get(f"/api/v1/incidents/{INCIDENT_ID}/root-cause")
        assert r.status_code == 200
        rc = r.json()
        assert rc["likely_cause"] == "PIPE-ZN-44"
        assert rc["confidence"] > 0.5

        # Step 2: Get national risk (should be high — crisis active)
        r = await client.get("/api/v1/risk")
        assert r.status_code == 200
        risk_before = r.json()
        assert risk_before["national"] > 50

        # Step 3: Generate solutions
        r = await client.get(f"/api/v1/solutions/{INCIDENT_ID}")
        assert r.status_code == 200
        solutions = r.json()
        assert len(solutions) >= 1

        # Step 4: Run simulation with best intervention
        sim_payload = {
            "incident_id": INCIDENT_ID,
            "intervention_id": "INT-A",
        }
        r = await client.post("/api/v1/simulations", json=sim_payload)
        assert r.status_code == 200
        sim = r.json()
        sim_id = sim["sim_id"]
        assert sim_id is not None
        # Risk after intervention should be lower than before
        assert sim["risk_after"] < risk_before["national"]

        # Step 5: Authorize decision
        dec_payload = {
            "incident_id": INCIDENT_ID,
            "intervention_id": "INT-A",
            "sim_id": sim_id,
            "justification": "Pipe burst critical, risk reduced via INT-A",
            "officer": "commander",
        }
        r = await client.post("/api/v1/decisions", json=dec_payload)
        assert r.status_code == 200
        decision = r.json()
        assert decision["status"] == "authorized"

    async def test_graph_integrity(self, client: AsyncClient):
        """Graph has correct node/edge counts from zarqa seed."""
        r = await client.get(f"/api/v1/incidents/{INCIDENT_ID}/graph")
        assert r.status_code == 200
        g = r.json()
        assert len(g["nodes"]) == 9
        assert len(g["edges"]) == 8

    async def test_signal_ingest_affects_risk(self, client: AsyncClient):
        """Ingesting a high-severity signal should be processed."""
        payload = {
            "id": "SIG-INTEG-01",
            "observes": "PIPE-ZN-44",
            "metric": "pressure_psi",
            "value": 5.0,
            "baseline": 45.0,
            "t_offset_s": 0,
            "severity_raw": 0.95,
        }
        r = await client.post("/api/v1/signals", json=payload)
        assert r.status_code == 200

        # Signal should appear in list
        r = await client.get("/api/v1/signals")
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert "SIG-INTEG-01" in ids
