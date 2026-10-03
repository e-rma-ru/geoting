from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import utcnow


class CompetitorMention(Base):
    __tablename__ = "competitor_mentions"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), index=True)
    competitor_name: Mapped[str] = mapped_column(String(255))
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recommendation_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
