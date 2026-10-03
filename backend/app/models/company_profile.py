from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import utcnow


class CompanyProfile(Base):
    """Aggregated AI presentation of one company across all runs of a research."""

    __tablename__ = "company_profiles"
    __table_args__ = (UniqueConstraint("research_id", "company_name", name="uq_profile_research_company"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    research_id: Mapped[int] = mapped_column(ForeignKey("research.id", ondelete="CASCADE"), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    top3_count: Mapped[int] = mapped_column(Integer, default=0)
    average_position: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_raw: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_heuristic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CompanyProfileFact(Base):
    """One normalized characteristic/fact of a company profile with frequency."""

    __tablename__ = "company_profile_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("company_profiles.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    normalized_label: Mapped[str] = mapped_column(String(255))
    frequency: Mapped[int] = mapped_column(Integer, default=0)
    frequency_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_mentions: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    run_ids: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
