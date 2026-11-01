"""Persistência: PostGIS em produção (docker-compose) e SQLite (GeoJSON em texto) para demo/testes."""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from shapely.geometry import MultiPolygon, mapping, shape
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.types import TypeDecorator

from .config import settings

Base = declarative_base()


def _now():
    return datetime.now(timezone.utc)


def _id():
    return uuid.uuid4().hex[:12]


class GeomType(TypeDecorator):
    """MULTIPOLYGON EPSG:4326: coluna `geometry` no PostGIS (índice GiST), texto GeoJSON no SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from geoalchemy2 import Geometry
            return dialect.type_descriptor(Geometry("MULTIPOLYGON", srid=4326))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return f"SRID=4326;{value.wkt}"
        return json.dumps(mapping(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            from geoalchemy2.shape import to_shape
            return to_shape(value)
        return shape(json.loads(value))


class Property(Base):
    __tablename__ = "properties"
    id = Column(String(12), primary_key=True, default=_id)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    geom = Column(GeomType, nullable=False)
    area_ha = Column(Float)
    is_demo = Column(String(1), default="0")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)
    plots = relationship("Plot", cascade="all, delete-orphan", back_populates="property", order_by="Plot.name")
    analyses = relationship("Analysis", cascade="all, delete-orphan", back_populates="property", order_by="Analysis.created_at.desc()")


class Plot(Base):
    __tablename__ = "plots"
    id = Column(String(12), primary_key=True, default=_id)
    property_id = Column(String(12), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    geom = Column(GeomType, nullable=False)
    area_ha = Column(Float)
    property = relationship("Property", back_populates="plots")


class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(String(12), primary_key=True, default=_id)
    property_id = Column(String(12), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="queued")  # queued|running|done|failed
    progress = Column(Float, default=0.0)
    stage = Column(String(200), default="Na fila")
    params = Column(JSON, default=dict)
    summary = Column(JSON, default=dict)
    error = Column(Text)
    mode = Column(String(10))
    created_at = Column(DateTime(timezone=True), default=_now)
    finished_at = Column(DateTime(timezone=True))
    property = relationship("Property", back_populates="analyses")


_engine = None
_Session = None


def init_db(url: str | None = None):
    global _engine, _Session
    url = url or settings.database_url
    if url.startswith("sqlite"):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        from sqlalchemy import event

        @event.listens_for(_engine, "connect")
        def _fk(dbapi, _):
            dbapi.execute("PRAGMA foreign_keys=ON")
    else:
        _engine = create_engine(url, pool_pre_ping=True)
        with _engine.begin() as c:
            c.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(_engine, expire_on_commit=False)
    return _engine


@contextmanager
def session():
    if _Session is None:
        init_db()
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
