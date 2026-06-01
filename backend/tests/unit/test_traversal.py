"""Unit tests for engine graph traversal — Tech Spec §1.3/§1.4."""
import json
import pytest
from app.engine.graph.store import CDG
from app.engine.graph.traversal import k_shortest_causal_paths, ancestors


@pytest.fixture
def seed():
    return json.load(open("data/seeds/zarqa.json"))


@pytest.fixture
def cdg(seed):
    return CDG.from_seed(seed["nodes"], seed["edges"])


class TestCDG:
    def test_build_from_seed(self, cdg):
        assert len(cdg.nodes) == 9
        assert len(cdg.out_edges("PIPE-ZN-44")) >= 1

    def test_out_edges(self, cdg):
        edges = cdg.out_edges("PIPE-ZN-44")
        assert any(e.dst == "PS-12" for e in edges)

    def test_in_edges(self, cdg):
        edges = cdg.in_edges("PS-12")
        assert any(e.src == "PIPE-ZN-44" for e in edges)

    def test_unknown_node_returns_empty(self, cdg):
        assert cdg.out_edges("NONEXIST") == []
        assert cdg.in_edges("NONEXIST") == []

    def test_edge_weight_bounds(self, cdg):
        for edges in cdg._out.values():
            for e in edges:
                assert 0.0 <= e.w <= 1.0
                assert e.lag_s >= 0


class TestTraversal:
    def test_hospital_to_pipe_path_weight(self, cdg):
        """Tech Spec §1.4: HOSP-ZN-1 → PIPE-ZN-44 path weight = 0.513."""
        paths = k_shortest_causal_paths(cdg, "HOSP-ZN-1", "PIPE-ZN-44", K=1)
        assert paths, "no causal path found"
        assert round(paths[0].path_weight, 3) == 0.513

    def test_911_to_pipe_path_exists(self, cdg):
        paths = k_shortest_causal_paths(cdg, "COMMS-911", "PIPE-ZN-44", K=1)
        assert paths, "no causal path from COMMS-911 to PIPE-ZN-44"
        assert paths[0].path_weight > 0

    def test_self_path_trivial(self, cdg):
        paths = k_shortest_causal_paths(cdg, "PIPE-ZN-44", "PIPE-ZN-44", K=1)
        assert len(paths) == 1
        assert paths[0].path_weight == 1.0

    def test_unreachable_returns_empty(self, cdg):
        paths = k_shortest_causal_paths(cdg, "PIPE-ZN-44", "COMMS-911", K=1)
        assert paths == []

    def test_ancestors_pipe(self, cdg):
        anc = ancestors(cdg, "COMMS-911")
        assert "POP-ZN" in anc

    def test_ancestors_top_has_none(self, cdg):
        anc = ancestors(cdg, "PIPE-ZN-44")
        assert len(anc) == 0

    def test_k_paths_multiple(self, cdg):
        paths = k_shortest_causal_paths(cdg, "HOSP-ZN-1", "PIPE-ZN-44", K=3)
        assert len(paths) >= 1
        for i in range(len(paths) - 1):
            assert paths[i].path_weight >= paths[i + 1].path_weight
