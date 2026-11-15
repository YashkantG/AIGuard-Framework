"""Data Provenance and Lineage Engine.

Lineage is a directed acyclic graph:

    Dataset -> Transformation -> Training Run -> Model Version -> Evaluation -> Deployment

Only metadata and SHA-256 fingerprints are stored; datasets are never copied.
"""

import hashlib
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aiguard.core.db import LineageEdgeRow, LineageNodeRow
from aiguard.core.errors import ConflictError, InvalidInputError, NotFoundError
from aiguard.security.integrity import calculate_model_hash

ALLOWED_EDGES: frozenset[tuple[str, str]] = frozenset(
    {
        ("dataset", "transformation"),
        ("dataset", "training_run"),
        ("dataset", "evaluation"),
        ("transformation", "transformation"),
        ("transformation", "dataset"),
        ("transformation", "training_run"),
        ("transformation", "evaluation"),
        ("training_run", "model_version"),
        ("model_version", "evaluation"),
        ("model_version", "deployment"),
        ("evaluation", "deployment"),
    }
)


def fingerprint_file(path: str | Path) -> str:
    return calculate_model_hash(path)


def fingerprint_directory(path: str | Path) -> str:
    """Digest of every file under ``path`` (relative names and contents, sorted)."""
    root = Path(path)
    digest = hashlib.sha256()
    for file in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(file.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(calculate_model_hash(file)))
    return digest.hexdigest()


def node_to_dict(row: LineageNodeRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "node_type": row.node_type,
        "name": row.name,
        "fingerprint": row.fingerprint,
        "model_id": row.model_id,
        "attributes": row.attributes,
        "created_at": row.created_at,
    }


def add_node(
    session: Session,
    *,
    node_type: str,
    name: str,
    fingerprint: str | None = None,
    model_id: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> LineageNodeRow:
    row = LineageNodeRow(
        id=f"ln_{uuid.uuid4().hex[:12]}",
        node_type=node_type,
        name=name,
        fingerprint=fingerprint.lower() if fingerprint else None,
        model_id=model_id,
        attributes=attributes or {},
    )
    session.add(row)
    session.flush()
    return row


def _neighbours(session: Session, node_id: str, *, upstream: bool) -> list[str]:
    if upstream:
        query = select(LineageEdgeRow.src_id).where(LineageEdgeRow.dst_id == node_id)
    else:
        query = select(LineageEdgeRow.dst_id).where(LineageEdgeRow.src_id == node_id)
    return list(session.execute(query).scalars())


def _reachable(session: Session, start: str, *, upstream: bool) -> set[str]:
    seen: set[str] = set()
    frontier = [start]
    while frontier:
        for neighbour in _neighbours(session, frontier.pop(), upstream=upstream):
            if neighbour not in seen:
                seen.add(neighbour)
                frontier.append(neighbour)
    return seen


def add_edge(session: Session, src_id: str, dst_id: str) -> LineageEdgeRow:
    """Link two nodes. Rejects unknown nodes, invalid stage order and cycles."""
    src = session.get(LineageNodeRow, src_id)
    dst = session.get(LineageNodeRow, dst_id)
    if src is None or dst is None:
        raise NotFoundError("Lineage node not found")
    if src_id == dst_id:
        raise InvalidInputError("A node cannot depend on itself")
    if (src.node_type, dst.node_type) not in ALLOWED_EDGES:
        raise InvalidInputError(f"{src.node_type} -> {dst.node_type} is not a valid lineage step")
    if dst_id in _neighbours(session, src_id, upstream=False):
        raise ConflictError("Edge already exists")
    if src_id in _reachable(session, dst_id, upstream=False):
        raise InvalidInputError("Edge would create a cycle")
    edge = LineageEdgeRow(src_id=src_id, dst_id=dst_id)
    session.add(edge)
    session.flush()
    return edge


def lineage_for_node(session: Session, node_id: str) -> dict[str, Any]:
    """Everything upstream and downstream of a node, plus a digest of its inputs."""
    if session.get(LineageNodeRow, node_id) is None:
        raise NotFoundError("Lineage node not found")
    upstream = _reachable(session, node_id, upstream=True)
    downstream = _reachable(session, node_id, upstream=False)
    ids = upstream | downstream | {node_id}
    nodes = session.execute(select(LineageNodeRow).where(LineageNodeRow.id.in_(ids))).scalars()
    node_dicts = sorted((node_to_dict(n) for n in nodes), key=lambda n: n["created_at"])
    edges = session.execute(
        select(LineageEdgeRow).where(
            LineageEdgeRow.src_id.in_(ids), LineageEdgeRow.dst_id.in_(ids)
        )
    ).scalars()

    # Digest over upstream fingerprints: changes if any input is swapped.
    digest = hashlib.sha256()
    upstream_nodes = [n for n in node_dicts if n["id"] in upstream]
    for node in sorted(upstream_nodes, key=lambda n: (n["node_type"], n["name"], n["id"])):
        digest.update(f"{node['node_type']}:{node['name']}:{node['fingerprint'] or ''}\n".encode())

    return {
        "root": node_id,
        "nodes": node_dicts,
        "edges": [{"src_id": e.src_id, "dst_id": e.dst_id} for e in edges],
        "upstream_ids": sorted(upstream),
        "downstream_ids": sorted(downstream),
        "has_dataset": any(n["node_type"] == "dataset" for n in upstream_nodes),
        "datasets_fingerprinted": all(
            n["fingerprint"] for n in upstream_nodes if n["node_type"] == "dataset"
        ),
        "lineage_digest": digest.hexdigest() if upstream_nodes else None,
    }
