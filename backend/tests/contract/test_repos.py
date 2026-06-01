"""Contract tests — verify memory repo implementations satisfy the protocol."""


class TestIncidentRepo:
    def test_list_all_returns_list(self, repos):
        result = repos.incidents.list_all()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_get_existing(self, repos):
        result = repos.incidents.get("INC-ZARQA-2026-05")
        assert result is not None
        assert result["id"] == "INC-ZARQA-2026-05"

    def test_get_nonexistent_returns_none(self, repos):
        assert repos.incidents.get("NONEXIST") is None

    def test_update(self, repos):
        repos.incidents.update("INC-ZARQA-2026-05", {"status": "resolved"})
        inc = repos.incidents.get("INC-ZARQA-2026-05")
        assert inc["status"] == "resolved"


class TestSignalRepo:
    def test_list_returns_signals(self, repos):
        sigs = repos.signals.list()
        assert isinstance(sigs, list)
        assert len(sigs) >= 1

    def test_add_signal(self, repos):
        from app.engine.types import Signal
        sig = Signal(
            id="TEST-SIG", observes="PIPE-ZN-44", metric="test",
            value=1.0, baseline=2.0, t_offset_s=0, severity_raw=0.5,
        )
        before = len(repos.signals.list())
        repos.signals.add(sig)
        after = len(repos.signals.list())
        assert after == before + 1


class TestSimulationRepo:
    def test_save_and_get(self, repos):
        repos.simulations.save("SIM-01", {"id": "SIM-01", "incident_id": "INC-ZARQA-2026-05"})
        result = repos.simulations.get("SIM-01")
        assert result is not None
        assert result["id"] == "SIM-01"

    def test_get_nonexistent(self, repos):
        assert repos.simulations.get("NONEXIST") is None

    def test_list_for_incident(self, repos):
        repos.simulations.save("SIM-02", {"id": "SIM-02", "incident_id": "INC-ZARQA-2026-05"})
        result = repos.simulations.list_for_incident("INC-ZARQA-2026-05")
        assert any(s["id"] == "SIM-02" for s in result)


class TestDecisionRepo:
    def test_save_and_get(self, repos):
        repos.decisions.save("DEC-01", {"id": "DEC-01", "authorized": True, "incident_id": "INC-ZARQA-2026-05"})
        result = repos.decisions.get("DEC-01")
        assert result is not None
        assert result["authorized"] is True

    def test_list_for_incident(self, repos):
        repos.decisions.save("DEC-02", {"id": "DEC-02", "incident_id": "INC-ZARQA-2026-05"})
        result = repos.decisions.list_for_incident("INC-ZARQA-2026-05")
        assert any(d["id"] == "DEC-02" for d in result)


class TestSourceRepo:
    def test_save_and_list(self, repos):
        repos.sources.save("SRC-01", {"id": "SRC-01", "name": "Test", "type": "api"})
        result = repos.sources.list_all()
        assert any(s["id"] == "SRC-01" for s in result)

    def test_delete(self, repos):
        repos.sources.save("SRC-DEL", {"id": "SRC-DEL", "name": "Del", "type": "api"})
        repos.sources.delete("SRC-DEL")
        assert repos.sources.get("SRC-DEL") is None


class TestGraphRepo:
    def test_get_nodes(self, repos):
        nodes = repos.graph.get_nodes()
        assert len(nodes) == 9

    def test_get_edges(self, repos):
        edges = repos.graph.get_edges()
        assert len(edges) == 8

    def test_get_node(self, repos):
        node = repos.graph.get_node("PIPE-ZN-44")
        assert node is not None


class TestInterventionRepo:
    def test_get_library(self, repos):
        lib = repos.interventions.get_library()
        assert isinstance(lib, list)
        assert len(lib) >= 1

    def test_list_for_incident(self, repos):
        result = repos.interventions.list_for_incident("INC-ZARQA-2026-05")
        assert isinstance(result, list)
