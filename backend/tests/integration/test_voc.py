"""Integration tests for VOC360 database endpoints."""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def voc_client():
    """Client with full lifespan (DB pool) for VOC tests."""
    from app.main import create_app
    from app.repositories.factory import get_repos
    from app.core import database as db_module

    # Reset the global engine so each test gets a fresh one on THIS event loop
    db_module._engine = None
    db_module._session_factory = None

    app = create_app()
    app.state.repos = get_repos()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Teardown: dispose engine to release connections
    await db_module.dispose_engine()


class TestVocSummary:
    async def test_summary_returns_counts(self, voc_client):
        r = await voc_client.get("/api/v1/voc/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total_records"] > 20000
        assert data["total_signals"] > 4000
        assert data["total_complaints"] > 3000
        assert data["total_clusters"] > 0
        assert len(data["severity_distribution"]) > 0
        assert len(data["top_entities"]) > 0


class TestVocKpi:
    async def test_kpi_returns_ministries(self, voc_client):
        r = await voc_client.get("/api/v1/voc/kpi")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 7
        ministries = {k["ministry"] for k in data}
        assert "MOH" in ministries
        assert "GAM" in ministries


class TestVocRecords:
    async def test_list_records_default(self, voc_client):
        r = await voc_client.get("/api/v1/voc/records")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0
        assert len(data["data"]) <= 50

    async def test_list_records_with_filter(self, voc_client):
        r = await voc_client.get("/api/v1/voc/records", params={"entity_id": "MOE"})
        assert r.status_code == 200
        data = r.json()
        for rec in data["data"]:
            assert rec["entity_id"] == "MOE"

    async def test_pagination(self, voc_client):
        r1 = await voc_client.get("/api/v1/voc/records", params={"limit": 5, "offset": 0})
        r2 = await voc_client.get("/api/v1/voc/records", params={"limit": 5, "offset": 5})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert len(r1.json()["data"]) == 5
        assert len(r2.json()["data"]) == 5


class TestVocSignals:
    async def test_list_signals_default(self, voc_client):
        r = await voc_client.get("/api/v1/voc/signals")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0

    async def test_filter_by_severity(self, voc_client):
        r = await voc_client.get("/api/v1/voc/signals", params={"severity": "critical"})
        assert r.status_code == 200
        data = r.json()
        for sig in data:
            assert sig["severity"] == "critical"


class TestVocComplaints:
    async def test_list_complaints_default(self, voc_client):
        r = await voc_client.get("/api/v1/voc/complaints")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0

    async def test_filter_by_ministry(self, voc_client):
        r = await voc_client.get("/api/v1/voc/complaints", params={"ministry": "GAM"})
        assert r.status_code == 200
        data = r.json()
        for c in data:
            assert c["ministry"] == "GAM"


class TestVocClusters:
    async def test_list_clusters(self, voc_client):
        r = await voc_client.get("/api/v1/voc/clusters")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0

    async def test_cluster_members(self, voc_client):
        # Get first cluster
        r = await voc_client.get("/api/v1/voc/clusters")
        clusters = r.json()
        cid = clusters[0]["cluster_id"]
        r2 = await voc_client.get(f"/api/v1/voc/clusters/{cid}/members")
        assert r2.status_code == 200


class TestVocForecasts:
    async def test_list_forecasts(self, voc_client):
        r = await voc_client.get("/api/v1/voc/forecasts")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0


class TestVocAnalytics:
    async def test_severity_distribution(self, voc_client):
        r = await voc_client.get("/api/v1/voc/analytics/severity")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        severities = {d["severity"] for d in data}
        assert "critical" in severities or "high" in severities

    async def test_governorate_breakdown(self, voc_client):
        r = await voc_client.get("/api/v1/voc/analytics/governorates")
        assert r.status_code == 200

    async def test_entity_breakdown(self, voc_client):
        r = await voc_client.get("/api/v1/voc/analytics/entities")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0

    async def test_signal_trend(self, voc_client):
        r = await voc_client.get("/api/v1/voc/analytics/trend", params={"days": 7})
        assert r.status_code == 200
