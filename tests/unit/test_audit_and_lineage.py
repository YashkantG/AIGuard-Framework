import pytest
from sqlalchemy import delete, update

from aiguard.audit import GENESIS_HASH, record_event, verify_chain
from aiguard.core.db import AuditRow, Database
from aiguard.core.errors import ConflictError, InvalidInputError, NotFoundError
from aiguard.provenance import add_edge, add_node, fingerprint_directory, lineage_for_node


@pytest.fixture
def db():
    return Database("sqlite://")


def add_events(db, count=4):
    with db.session() as session:
        for i in range(count):
            record_event(
                session, actor="t", category="c", action=f"a{i}", result="success",
                details={"i": i, "nested": {"x": 1.5}},
            )  # fmt: skip


def test_chain_links_and_verifies(db):
    add_events(db)
    with db.session() as session:
        rows = session.query(AuditRow).order_by(AuditRow.seq).all()
        assert rows[0].prev_hash == GENESIS_HASH
        assert all(b.prev_hash == a.event_hash for a, b in zip(rows, rows[1:], strict=False))
        result = verify_chain(session)
    assert result["valid"] and result["events_checked"] == 4
    assert result["head_hash"] == rows[-1].event_hash


def test_empty_chain_is_valid(db):
    with db.session() as session:
        assert verify_chain(session)["valid"]


@pytest.mark.parametrize("column,value", [("result", "failure"), ("actor", "mallory")])
def test_edited_event_is_detected(db, column, value):
    add_events(db)
    with db.session() as session:
        session.execute(update(AuditRow).where(AuditRow.seq == 2).values({column: value}))
    with db.session() as session:
        result = verify_chain(session)
    assert not result["valid"]
    assert result["first_invalid_seq"] == 2


def test_deleted_event_is_detected(db):
    add_events(db)
    with db.session() as session:
        session.execute(delete(AuditRow).where(AuditRow.seq == 2))
    with db.session() as session:
        result = verify_chain(session)
    assert not result["valid"]
    assert result["first_invalid_seq"] == 3
    assert "removed or reordered" in result["reason"]


def build_chain(session):
    data = add_node(session, node_type="dataset", name="d", fingerprint="A" * 64)
    prep = add_node(session, node_type="transformation", name="p")
    run = add_node(session, node_type="training_run", name="r")
    model = add_node(session, node_type="model_version", name="m:1", model_id="mdl_1")
    for src, dst in [(data, prep), (prep, run), (run, model)]:
        add_edge(session, src.id, dst.id)
    return data, prep, run, model


def test_lineage_traces_upstream_and_downstream(db):
    with db.session() as session:
        data, prep, run, model = build_chain(session)
        deploy = add_node(session, node_type="deployment", name="prod")
        add_edge(session, model.id, deploy.id)
        result = lineage_for_node(session, model.id)

        assert set(result["upstream_ids"]) == {data.id, prep.id, run.id}
        assert result["downstream_ids"] == [deploy.id]
        assert result["has_dataset"] and result["datasets_fingerprinted"]
        assert data.fingerprint == "a" * 64  # normalised to lower case
        assert len(result["edges"]) == 4

        # Swapping an input changes the digest.
        before = result["lineage_digest"]
        data.fingerprint = "b" * 64
        session.flush()
        assert lineage_for_node(session, model.id)["lineage_digest"] != before


def test_lineage_rejects_invalid_edges(db):
    with db.session() as session:
        data, prep, run, model = build_chain(session)
        with pytest.raises(InvalidInputError, match="not a valid lineage step"):
            add_edge(session, model.id, data.id)
        with pytest.raises(InvalidInputError):
            add_edge(session, prep.id, prep.id)
        with pytest.raises(ConflictError):
            add_edge(session, data.id, prep.id)
        with pytest.raises(NotFoundError):
            add_edge(session, data.id, "ln_missing")
        # transformation -> dataset is allowed, but not when it closes a loop.
        with pytest.raises(InvalidInputError, match="cycle"):
            add_edge(session, prep.id, data.id)


def test_directory_fingerprint_is_content_and_name_sensitive(tmp_path):
    (tmp_path / "a.csv").write_text("1,2,3")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.csv").write_text("4,5,6")
    first = fingerprint_directory(tmp_path)
    assert fingerprint_directory(tmp_path) == first

    (tmp_path / "sub" / "b.csv").write_text("4,5,7")
    changed = fingerprint_directory(tmp_path)
    assert changed != first

    (tmp_path / "sub" / "b.csv").rename(tmp_path / "sub" / "c.csv")
    assert fingerprint_directory(tmp_path) != changed
