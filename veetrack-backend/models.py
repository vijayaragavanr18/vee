from datetime import datetime
import uuid
from typing import List, Optional, Any
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Boolean, Text, JSON, LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

def _uuid_str() -> str:
    return str(uuid.uuid4())

# ── 1. Core Domain Models ──────────────────────────────────────────

class Article(Base):
    __tablename__ = "articles"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    url: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String)
    body_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # NLP outputs
    sentiment_label: Mapped[Optional[str]] = mapped_column(String)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer)
    trend_score: Mapped[Optional[int]] = mapped_column(Integer)
    summary: Mapped[Optional[str]] = mapped_column(Text)

class Entity(Base):
    __tablename__ = "entities"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[str] = mapped_column(String)

class IntelligenceCard(Base):
    __tablename__ = "intelligence_cards"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), unique=True)
    executive_summary: Mapped[str] = mapped_column(Text)
    key_takeaways: Mapped[List[str]] = mapped_column(JSON)
    sentiment: Mapped[str] = mapped_column(String)
    risk_level: Mapped[str] = mapped_column(String)
    recommended_actions: Mapped[List[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# ── 2. Clustering & HDBSCAN Models ────────────────────────────────

class ClusterVersion(Base):
    __tablename__ = "cluster_versions"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    window_start: Mapped[datetime] = mapped_column(DateTime)
    window_end: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ClusterAssignment(Base):
    __tablename__ = "cluster_assignments"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    version_id: Mapped[str] = mapped_column(ForeignKey("cluster_versions.id", ondelete="CASCADE"))
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    cluster_id: Mapped[int] = mapped_column(Integer, index=True)
    centroid: Mapped[Optional[bytes]] = mapped_column(LargeBinary) # Stored as numpy array blob

# ── 3. Deduplication Models ───────────────────────────────────────

class DedupRecord(Base):
    __tablename__ = "dedup_records"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), unique=True)
    canonical_id: Mapped[Optional[str]] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"))
    dedup_type: Mapped[str] = mapped_column(String) # "minhash", "semantic", "unique"
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# ── 4. Ingestion Source Models ────────────────────────────────────

class NewsSource(Base):
    __tablename__ = "news_sources"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String) # "rss", "newsapi", "url"
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_fetched: Mapped[Optional[datetime]] = mapped_column(DateTime)

class FetchLog(Base):
    __tablename__ = "fetch_logs"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    source_id: Mapped[str] = mapped_column(ForeignKey("news_sources.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String) # "success", "error"
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    articles_found: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# ── 5. Graph Storage Models ───────────────────────────────────────

class EntityNode(Base):
    __tablename__ = "entity_nodes"
    
    name: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class EntityEdge(Base):
    __tablename__ = "entity_edges"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    source: Mapped[str] = mapped_column(ForeignKey("entity_nodes.name"), index=True)
    target: Mapped[str] = mapped_column(ForeignKey("entity_nodes.name"), index=True)
    relation_type: Mapped[str] = mapped_column(String, default="co-occurrence")
    weight: Mapped[int] = mapped_column(Integer, default=1)
    article_count: Mapped[int] = mapped_column(Integer, default=1)

# ── 6. Auth & RBAC Models ─────────────────────────────────────────

class Role(Base):
    __tablename__ = "roles"
    
    name: Mapped[str] = mapped_column(String, primary_key=True) # "admin", "analyst", "viewer"

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    role_name: Mapped[str] = mapped_column(ForeignKey("roles.name"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    key_hash: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
