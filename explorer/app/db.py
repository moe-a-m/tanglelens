import os
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, String, Text,
                        create_engine, inspect, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./explorer.db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True,
                       connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def utcnow() -> datetime:
    """All timestamps are stored as naive UTC for portability across SQLite/Postgres."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime | None) -> str | None:
    """API format for a stored (naive UTC) timestamp."""
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    block_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)

    # What the explorer received (human readable + exact bytes sent to Hornet)
    tag: Mapped[str] = mapped_column(String(128), index=True)
    tag_hex: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    payload_text: Mapped[str] = mapped_column(Text)          # for free-text search
    data_hex: Mapped[str] = mapped_column(Text)
    data_sha256: Mapped[str] = mapped_column(String(64), index=True)

    # Enrichment metadata (not on the Tangle)
    message_type: Mapped[str | None] = mapped_column(String(64), index=True)
    source: Mapped[str | None] = mapped_column(String(128), index=True)
    node: Mapped[str | None] = mapped_column(String(128))
    trace_id: Mapped[str | None] = mapped_column(String(128), index=True)   # groups related events (D8)
    received_via: Mapped[str | None] = mapped_column(String(8))             # http | mqtt: first path to arrive (D12)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Latest verification state against the Tangle
    status: Mapped[str] = mapped_column(String(32), index=True, default="unverified")
    is_solid: Mapped[bool | None] = mapped_column(Boolean)
    milestone_index: Mapped[int | None] = mapped_column(Integer)
    milestone_time: Mapped[datetime | None] = mapped_column(DateTime)
    ledger_inclusion_state: Mapped[str | None] = mapped_column(String(32))
    content_match: Mapped[bool | None] = mapped_column(Boolean)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    check_count: Mapped[int] = mapped_column(Integer, default=0)

    validations: Mapped[list["Validation"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", order_by="Validation.id.desc()")


class Validation(Base):
    """Audit trail: every check against Hornet is recorded, never overwritten."""
    __tablename__ = "validations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(32))
    is_solid: Mapped[bool | None] = mapped_column(Boolean)
    referenced_by_milestone_index: Mapped[int | None] = mapped_column(Integer)
    ledger_inclusion_state: Mapped[str | None] = mapped_column(String(32))
    tag_match: Mapped[bool | None] = mapped_column(Boolean)
    data_match: Mapped[bool | None] = mapped_column(Boolean)
    detail: Mapped[str | None] = mapped_column(Text)

    message: Mapped[Message] = relationship(back_populates="validations")


class Alert(Base):
    """Notification of a critical event (DESIGN D10). Append-only except acknowledged_at."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(16))                 # integrity | application
    status: Mapped[str] = mapped_column(String(32))               # message status when raised
    previous_status: Mapped[str | None] = mapped_column(String(32))
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), index=True)
    block_id: Mapped[str] = mapped_column(String(80))
    tag: Mapped[str] = mapped_column(String(128))
    trace_id: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)


def init_db() -> None:
    Base.metadata.create_all(engine)
    add_missing_columns()


def add_missing_columns() -> list[str]:
    """Additive upgrade of an existing database (DESIGN D11): add nullable columns that the
    models define but the tables lack. Never drops or alters anything."""
    added = []
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing and col.nullable:
                    ddl = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl}'))
                    if col.index:
                        conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_{table.name}_{col.name} '
                                          f'ON {table.name} ({col.name})'))
                    added.append(f"{table.name}.{col.name}")
    return added
