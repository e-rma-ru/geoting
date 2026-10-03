from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.citation import Citation
from app.models.competitor_mention import CompetitorMention
from app.models.mention_analysis import MentionAnalysis
from app.models.project import Project
from app.models.prompt import Prompt
from app.models.research_run import ResearchRun
from app.providers.base import AIResponse
from app.services import analyzer as analyzer_module
from app.services.branding import (
    brand_mentioned_in_string,
    detect_brand_mention,
    mentions_any_alias,
)
from app.utils.net import extract_domain, infer_source_type

logger = logging.getLogger("geoting.analysis")


class AnalysisService:
    def __init__(self, db: AsyncSession, project: Project, prompt: Prompt, run: ResearchRun, ai_response: AIResponse):
        self.db = db
        self.project = project
        self.prompt = prompt
        self.research_run = run
        self.ai_response = ai_response
        self.aliases: List[str] = [a for a in (project.brand_aliases or []) if a]

    async def run(self) -> MentionAnalysis:
        text = self.ai_response.text or ""

        logger.info("[run %s] Analysis started", self.research_run.id)
        brand_mentioned, _ = detect_brand_mention(text, self.aliases)

        llm: Optional[Dict[str, Any]] = None
        try:
            llm = await analyzer_module.analyze_with_llm(
                company_name=self.project.name,
                website=self.project.website,
                city=self.project.city,
                description=self.project.description,
                brand_aliases=self.aliases,
                prompt_text=self.prompt.text,
                answer_text=text,
                sources=[s.dict() for s in self.ai_response.sources],
            )
        except Exception as exc:
            logger.warning("[run %s] Analyzer exception: %s", self.research_run.id, exc)

        is_heuristic = llm is None
        analysis = self._build_analysis(brand_mentioned, llm, text)

        # Citations
        self._save_citations(text)

        # Competitors
        self._save_competitors(llm)

        self.db.add(analysis)
        await self.db.commit()
        logger.info("[run %s] Analysis completed (heuristic=%s)", self.research_run.id, is_heuristic)
        return analysis

    def _build_analysis(
        self, brand_mentioned: bool, llm: Optional[Dict[str, Any]], text: str
    ) -> MentionAnalysis:
        if llm:
            try:
                llm_mentioned = bool(llm.get("brand_mentioned"))
            except Exception:
                llm_mentioned = False

            # brand_mentioned is programmatically authoritative; the LLM result
            # is stored in raw_analysis for reference.
            recommendation_score = self._clamp_int(llm.get("recommendation_score"), 0, 5)
            accuracy_score = self._clamp_int(llm.get("accuracy_score"), 0, 100)
            brand_position = self._nullable_int(llm.get("brand_position"))
            confidence = self._clamp_float(llm.get("confidence"))
            sentiment = str(llm.get("sentiment") or "unknown")
            reasoning = str(llm.get("reasoning") or "")

            if not brand_mentioned:
                recommendation_score = 0
                brand_position = None

            return MentionAnalysis(
                research_run_id=self.research_run.id,
                brand_mentioned=brand_mentioned,
                brand_position=brand_position,
                recommendation_score=recommendation_score,
                sentiment=sentiment if sentiment in ("positive", "neutral", "negative", "mixed", "unknown") else "unknown",
                accuracy_score=accuracy_score,
                confidence=confidence,
                reasoning=reasoning,
                is_heuristic=False,
                raw_analysis=llm,
            )

        # Heuristic-only fallback (no analyzer configured/failed).
        return MentionAnalysis(
            research_run_id=self.research_run.id,
            brand_mentioned=brand_mentioned,
            brand_position=None,
            recommendation_score=1 if brand_mentioned else 0,
            sentiment="unknown",
            accuracy_score=None,
            confidence=None,
            reasoning=(
                "Heuristic only: brand presence detected programmatically via aliases. "
                "LLM analysis is not configured or failed."
            ),
            is_heuristic=True,
            raw_analysis=None,
        )

    def _save_citations(self, text: str) -> None:
        project_domain = extract_domain(self.project.website) or ""
        for source in self.ai_response.sources:
            url = source.url
            domain = extract_domain(url)
            title = source.title
            cited_text = source.cited_text

            supports_brand: Optional[bool] = False
            if domain and project_domain and domain == project_domain:
                supports_brand = True
            elif domain and self._domain_matches_brand(domain):
                supports_brand = True
            elif url and brand_mentioned_in_string(url, self.aliases):
                supports_brand = True
            elif (title and mentions_any_alias(title, self.aliases)) or (cited_text and mentions_any_alias(cited_text, self.aliases)):
                supports_brand = True

            self.db.add(
                Citation(
                    research_run_id=self.research_run.id,
                    url=url,
                    domain=domain,
                    title=title,
                    cited_text=cited_text,
                    supports_brand=supports_brand,
                    source_type=infer_source_type(domain),
                )
            )

    def _domain_matches_brand(self, domain: str) -> bool:
        """True if the domain contains a brand-like alias token."""
        d = domain.lower()
        for alias in self.aliases:
            token = alias.strip().lower().replace(" ", "").replace("-", "")
            if token and len(token) >= 4 and token in d.replace("-", ""):
                return True
        return False

    def _save_competitors(self, llm: Optional[Dict[str, Any]]) -> None:
        competitors = []
        if llm:
            competitors = llm.get("competitors") or []
        for comp in competitors:
            name = str(comp.get("name") or "").strip()
            if not name:
                continue
            self.db.add(
                CompetitorMention(
                    research_run_id=self.research_run.id,
                    competitor_name=name,
                    position=self._nullable_int(comp.get("position")),
                    recommendation_score=self._nullable_int(comp.get("recommendation_score")),
                )
            )

    @staticmethod
    def _clamp_int(value: Any, lo: int, hi: int) -> int:
        try:
            v = int(value)
        except (TypeError, ValueError):
            return lo
        return max(lo, min(hi, v))

    @staticmethod
    def _clamp_float(value: Any) -> Optional[float]:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, min(1.0, v))

    @staticmethod
    def _nullable_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            v = int(value)
        except (TypeError, ValueError):
            return None
        return v if v > 0 else None
