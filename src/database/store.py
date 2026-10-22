from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from src.settings import settings


class Base(DeclarativeBase):
    pass


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[str] = mapped_column(String(80), index=True)
    date: Mapped[object] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(500))
    units: Mapped[str] = mapped_column(String(100))
    quality: Mapped[str] = mapped_column(String(40), default="AVAILABLE / DELAYED")
    # Local retrieval vintages, not ALFRED real-time vintages.
    __table_args__ = (UniqueConstraint("series_id", "date", "retrieved_at"),)


class Job(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[str] = mapped_column(String(80), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class ResearchRecord(Base):
    """Versioned research definitions, events, assumptions and settings."""

    __tablename__ = "research_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(200))
    payload: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (UniqueConstraint("kind", "name", "version"),)


class WorkbookImport(Base):
    """Immutable local import snapshots, kept separate from independent provider observations."""

    __tablename__ = "workbook_imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)


if settings.database_url.startswith("sqlite:///data/"):
    Path("data").mkdir(exist_ok=True)
engine = create_engine(
    settings.database_url,
    connect_args={"timeout": 30} if settings.database_url.startswith("sqlite") else {},
)


def initialize():
    Base.metadata.create_all(engine)


def history(series_id):
    import pandas as pd

    with Session(engine) as session:
        rows = session.scalars(
            select(Observation)
            .where(Observation.series_id == series_id)
            .order_by(Observation.date, Observation.retrieved_at, Observation.id)
        ).all()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(
            [
                {
                    "date": r.date,
                    "value": r.value,
                    "retrieved_at": r.retrieved_at,
                    "published_at": r.published_at,
                    "source": r.source,
                    "units": r.units,
                    "quality": r.quality,
                }
                for r in rows
            ]
        )
    df["date"] = pd.to_datetime(df["date"])
    return df.drop_duplicates("date", keep="last").set_index("date")


def save(series, frame):
    now = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        prior = {
            r.date: r.value
            for r in session.scalars(
                select(Observation)
                .where(Observation.series_id == series["id"])
                .order_by(Observation.retrieved_at, Observation.id)
            )
        }
        count = 0
        for date, value in frame.items():
            d = date.date()
            if prior.get(d) != float(value):
                session.add(
                    Observation(
                        series_id=series["id"],
                        date=d,
                        value=float(value),
                        retrieved_at=now,
                        source=series["url"],
                        units=series["unit"],
                    )
                )
                count += 1
        session.add(Job(series_id=series["id"], started_at=now, status="success", count=count))
    return count
