"""Hash-chained audit log.

Every event stores the hash of the previous event, so editing, deleting or
reordering a record breaks the chain and is detected by :func:`verify_chain`.

This gives tamper *evidence*, not tamper *prevention*: someone with full write
access to the database can rewrite the whole chain consistently. Anchor the
latest ``event_hash`` somewhere they cannot reach (a separate system, a signed
release note) if you need to detect that as well.
"""

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aiguard.core.db import AuditRow, utcnow_iso

GENESIS_HASH = "0" * 64

_HASHED_FIELDS = (
    "id",
    "timestamp",
    "actor",
    "model_id",
    "model_version",
    "category",
    "action",
    "result",
    "evidence_refs",
    "details",
    "prev_hash",
)


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_event_hash(fields: dict[str, Any]) -> str:
    payload = {name: fields[name] for name in _HASHED_FIELDS}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def event_to_dict(row: AuditRow) -> dict[str, Any]:
    data = {name: getattr(row, name) for name in _HASHED_FIELDS}
    data["seq"] = row.seq
    data["event_hash"] = row.event_hash
    return data


def record_event(
    session: Session,
    *,
    actor: str,
    category: str,
    action: str,
    result: str,
    model_id: str | None = None,
    model_version: str | None = None,
    evidence_refs: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> AuditRow:
    """Append an event to the chain. The caller owns the transaction."""
    last = session.execute(
        select(AuditRow).order_by(AuditRow.seq.desc()).limit(1)
    ).scalar_one_or_none()
    fields: dict[str, Any] = {
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "timestamp": utcnow_iso(),
        "actor": actor,
        "model_id": model_id,
        "model_version": model_version,
        "category": category,
        "action": action,
        "result": result,
        "evidence_refs": list(evidence_refs or []),
        # Round-trip through JSON so the hash covers exactly what is stored.
        "details": json.loads(canonical_json(details or {})),
        "prev_hash": last.event_hash if last else GENESIS_HASH,
    }
    row = AuditRow(**fields, event_hash=compute_event_hash(fields))
    session.add(row)
    session.flush()
    return row


def verify_chain(session: Session) -> dict[str, Any]:
    """Recompute every hash and link. Returns the first inconsistency found."""
    expected_prev = GENESIS_HASH
    checked = 0
    for row in session.execute(select(AuditRow).order_by(AuditRow.seq)).scalars():
        fields = {name: getattr(row, name) for name in _HASHED_FIELDS}
        if row.prev_hash != expected_prev:
            return {
                "valid": False,
                "events_checked": checked,
                "first_invalid_seq": row.seq,
                "reason": "Link to previous event is broken (event removed or reordered).",
            }
        if compute_event_hash(fields) != row.event_hash:
            return {
                "valid": False,
                "events_checked": checked,
                "first_invalid_seq": row.seq,
                "reason": "Event content does not match its recorded hash.",
            }
        expected_prev = row.event_hash
        checked += 1
    return {
        "valid": True,
        "events_checked": checked,
        "first_invalid_seq": None,
        "reason": "",
        "head_hash": expected_prev,
    }
