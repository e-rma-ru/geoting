from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import utcnow


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), index=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cited_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supports_brand: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
