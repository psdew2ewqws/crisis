"""Smoke tests — verify every API endpoint returns expected status codes."""
from httpx import AsyncClient

INCIDENT_ID = "INC-ZARQA-2026-05"


class TestHealthEndpoint:
    async def test_health_ok(self, client: AsyncClient):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestIncidentsAPI:
    async def test_list_incidents(self, client: AsyncClient):
        r = await client.get("/api/v1/incidents")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_incident(self, client: AsyncClient):
        r = await client.get(f"/api/v1/incidents/{INCIDENT_ID}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == INCIDENT_ID

    async def test_get_incident_not_found(self, client: AsyncClient):
        r = await client.get("/api/v1/incidents/NONEXIST")
        assert r.status_code == 404

    async def test_get_incident_graph(self, client: AsyncClient):
        r = await client.get(f"/api/v1/incidents/{INCIDENT_ID}/graph")
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data
        assert "edges" in data

    async def test_get_root_cause(self, client: AsyncClient):
        r = await client.get(f"/api/v1/incidents/{INCIDENT_ID}/root-cause")
        assert r.status_code == 200
        data = r.json()
        assert "likely_cause" in data
        assert data["likely_cause"] == "PIPE-ZN-44"


class TestSignalsAPI:
    async def test_list_signals(self, client: AsyncClient):
        r = await client.get("/api/v1/signals")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_list_signals_with_since(self, client: AsyncClient):
        r = await client.get("/api/v1/signals", params={"since": 999999999.0})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    async def test_ingest_signal(self, client: AsyncClient):
        payload = {
            "id": "SIG-TEST-01",
            "observes": "PIPE-ZN-44",
            "metric": "pressure_psi",
            "value": 10.0,
            "baseline": 45.0,
            "t_offset_s": 0,
            "severity_raw": 0.9,
        }
        r = await client.post("/api/v1/signals", json=payload)
        assert r.status_code == 200


class TestRiskAPI:
    async def test_get_risk(self, client: AsyncClient):
        r = await client.get("/api/v1/risk")
        assert r.status_code == 200
        data = r.json()
        assert "national" in data
        assert data["national"] > 0


class TestSolutionsAPI:
    async def test_list_solutions(self, client: AsyncClient):
        r = await client.get(f"/api/v1/solutions/{INCIDENT_ID}")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_generate_solutions(self, client: AsyncClient):
        r = await client.post(f"/api/v1/solutions/{INCIDENT_ID}/generate")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    async def test_solutions_not_found(self, client: AsyncClient):
        r = await client.get("/api/v1/solutions/NONEXIST")
        assert r.status_code == 404


class TestSimulationsAPI:
    async def test_create_simulation(self, client: AsyncClient):
        payload = {
            "incident_id": INCIDENT_ID,
            "intervention_id": "INT-A",
        }
        r = await client.post("/api/v1/simulations", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "sim_id" in data
        assert "risk_after" in data

    async def test_create_simulation_not_found(self, client: AsyncClient):
        payload = {
            "incident_id": "NONEXIST",
            "intervention_id": "INT-A",
        }
        r = await client.post("/api/v1/simulations", json=payload)
        assert r.status_code == 404


class TestDecisionsAPI:
    async def test_create_decision(self, client: AsyncClient):
        # First create a simulation so we have a sim_id
        sim_payload = {
            "incident_id": INCIDENT_ID,
            "intervention_id": "INT-A",
        }
        sim_r = await client.post("/api/v1/simulations", json=sim_payload)
        sim_data = sim_r.json()
        sim_id = sim_data["sim_id"]

        payload = {
            "incident_id": INCIDENT_ID,
            "intervention_id": "INT-A",
            "sim_id": sim_id,
            "justification": "Critical infrastructure at risk",
            "officer": "commander",
        }
        r = await client.post("/api/v1/decisions", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "authorized"

    async def test_get_decision_not_found(self, client: AsyncClient):
        r = await client.get("/api/v1/decisions/NONEXIST")
        assert r.status_code == 404


class TestSourcesAPI:
    async def test_list_sources_empty(self, client: AsyncClient):
        r = await client.get("/api/v1/sources")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_register_source(self, client: AsyncClient):
        payload = {
            "id": "SRC-TEST-01",
            "name": "Test Sensor",
            "type": "iot_sensor",
            "config": {"endpoint": "mqtt://test"},
        }
        r = await client.post("/api/v1/sources", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "SRC-TEST-01"
        assert data["status"] == "registered"

    async def test_source_persists(self, client: AsyncClient):
        payload = {
            "id": "SRC-PERSIST",
            "name": "Persist Check",
            "type": "api",
        }
        await client.post("/api/v1/sources", json=payload)
        r = await client.get("/api/v1/sources")
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert "SRC-PERSIST" in ids
