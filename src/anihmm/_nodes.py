from __future__ import annotations

NodeParts = tuple[str, int | None]


def parse_node_id(node_id: object) -> NodeParts | None:
    """Parse a canonical ASCII HMM node identifier."""
    if not isinstance(node_id, str):
        return None
    if node_id in {"S", "E"}:
        return node_id, None
    if len(node_id) < 2 or node_id[0] not in {"D", "I", "M"}:
        return None

    suffix = node_id[1:]
    if not suffix.isascii() or not suffix.isdigit():
        return None
    if len(suffix) > 1 and suffix.startswith("0"):
        return None

    index = int(suffix)
    if node_id[0] in {"D", "M"} and index < 1:
        return None
    return node_id[0], index
