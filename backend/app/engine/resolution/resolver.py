def resolve(raw: str, known_nodes: dict[str, str] | None = None) -> str:
    """Map free-text/source entity name to a CDG node ID.
    For now: exact-match dictionary. Splink probabilistic linkage later."""
    if known_nodes and raw in known_nodes:
        return known_nodes[raw]
    # Default: identity (raw is already a node ID)
    return raw
