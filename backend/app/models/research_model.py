from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import utcnow


class ResearchModel(Base):
    """An AI model selected to run in a research (experiment participant).

    One Research may contain several models; each ResearchRun records exactly
    which model produced it via `research_runs.model`.
    """

    __tablename__ = "research_models"
    __table_args__ = (UniqueConstraint("research_id", "model", name="uq_research_model"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    research_id: Mapped[int] = mapped_column(ForeignKey("research.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(255))
    # Gateway the model is served through. Always "routerai" for new rows;
    # NULL for legacy rows migrated from a pre-RouterAI single-model research.
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
