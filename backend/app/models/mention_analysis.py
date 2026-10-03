from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import utcnow


class MentionAnalysis(Base):
    __tablename__ = "mention_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), index=True, unique=True)
    brand_mentioned: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    brand_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recommendation_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    accuracy_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_heuristic: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_analysis: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
