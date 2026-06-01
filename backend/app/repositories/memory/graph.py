from app.engine.types import Node, Edge
from app.repositories.memory.store import MemoryStore


class MemoryGraphRepo:
    def __init__(self, store: MemoryStore):
        self._store = store

    def get_nodes(self) -> list[Node]:
        return list(self._store.cdg.nodes.values()) if self._store.cdg else []

    def get_edges(self) -> list[Edge]:
        if not self._store.cdg:
            return []
        edges = []
        for edge_list in self._store.cdg._out.values():
            edges.extend(edge_list)
        return edges

    def get_node(self, node_id: str) -> Node | None:
        if self._store.cdg:
            return self._store.cdg.nodes.get(node_id)
        return None
