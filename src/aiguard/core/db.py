"""SQLAlchemy persistence layer.

SQLite is used by default so the framework runs with no setup. Point
``AIGUARD_DATABASE_URL`` at PostgreSQL for shared deployments.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Base(DeclarativeBase):
    pass


class ModelRow(Base):
    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_model_name_version"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    version: Mapped[str] = mapped_column(String(50))
    framework: Mapped[str] = mapped_column(String(50), default="unknown")
    artifact_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    intended_use: Mapped[str] = mapped_column(Text, default="")
    impact_tier: Mapped[str] = mapped_column(String(20), default="limited")
    human_oversight: Mapped[str] = mapped_column(Text, default="")
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso)
    created_by: Mapped[str] = mapped_column(String(200), default="")


class EvidenceRow(Base):
    __tablename__ = "evidence"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(40), unique=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    actor: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso)


class AuditRow(Base):
    __tablename__ = "audit_events"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(40), unique=True)
    timestamp: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(200))
    model_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(80))
    result: Mapped[str] = mapped_column(String(40))
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: Unique so that two writers cannot both extend the same chain head.
    prev_hash: Mapped[str] = mapped_column(String(64), unique=True)
    event_hash: Mapped[str] = mapped_column(String(64))


class LineageNodeRow(Base):
    __tablename__ = "lineage_nodes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    node_type: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(200))
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso)


class LineageEdgeRow(Base):
    __tablename__ = "lineage_edges"
    __table_args__ = (UniqueConstraint("src_id", "dst_id", name="uq_lineage_edge"),)

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    src_id: Mapped[str] = mapped_column(ForeignKey("lineage_nodes.id"), index=True)
    dst_id: Mapped[str] = mapped_column(ForeignKey("lineage_nodes.id"), index=True)


class Database:
    def __init__(self, url: str) -> None:
        kwargs: dict[str, Any] = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url or url == "sqlite://":
                kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, **kwargs)
        self._factory = sessionmaker(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
