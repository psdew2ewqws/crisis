from app.engine.types import Node, Edge


class CDG:
    """Crisis Dependency Graph — directed, weighted, typed (Tech Spec §1.1)."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self._out: dict[str, list[Edge]] = {}
        self._in: dict[str, list[Edge]] = {}

    def add_node(self, n: Node) -> None:
        self.nodes[n.id] = n
        self._out.setdefault(n.id, [])
        self._in.setdefault(n.id, [])

    def add_edge(self, e: Edge) -> None:
        assert 0.0 <= e.w <= 1.0 and e.lag_s >= 0, "R1: bad edge weight/lag"
        self._out.setdefault(e.src, []).append(e)
        self._in.setdefault(e.dst, []).append(e)

    def out_edges(self, nid: str) -> list[Edge]:
        return self._out.get(nid, [])

    def in_edges(self, nid: str) -> list[Edge]:
        return self._in.get(nid, [])

    @classmethod
    def from_seed(cls, nodes: list[dict], edges: list[dict]) -> "CDG":
        g = cls()
        for n in nodes:
            g.add_node(Node(
                id=n["id"], type=n["type"], kind=n["kind"],
                label=n.get("label", ""), location_ref=n.get("location_ref"),
                attrs=n.get("attrs", {}),
            ))
        for e in edges:
            g.add_edge(Edge(
                src=e["src"], dst=e["dst"], rel=e["rel"],
                w=e["w"], lag_s=e["lag_s"],
            ))
        return g
