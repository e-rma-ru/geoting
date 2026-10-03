from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ResearchCreate(BaseModel):
    project_id: int
    name: Optional[str] = None
    # RouterAI model ids in `provider/model` form (e.g. deepseek/deepseek-v4-flash).
    # At least one model is required. When omitted, `model` (legacy) or the
    # configured default model is used.
    models: Optional[List[str]] = Field(default=None)
    model: Optional[str] = Field(default=None, max_length=255)  # legacy single-model field
    runs_per_prompt: int = Field(default=3, ge=1, le=10)


class ResearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    status: str
    models: List[str] = Field(default_factory=list)
    prompts_count: int
    providers_count: int
    runs_per_prompt: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class ResearchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    research_id: int
    prompt_id: int
    provider: str
    model: Optional[str] = None
    run_number: int
    status: str
    response_text: Optional[str] = None
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ResearchRunDetail(ResearchRunRead):
    raw_response: Optional[object] = None


class RunPromptInfo(BaseModel):
    id: Optional[int] = None
    text: Optional[str] = None
    cluster: Optional[str] = None
    intent: Optional[str] = None


class RunAnalysisInfo(BaseModel):
    id: Optional[int] = None
    brand_mentioned: Optional[bool] = None
    brand_position: Optional[int] = None
    recommendation_score: Optional[int] = None
    sentiment: Optional[str] = None
    accuracy_score: Optional[int] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    is_heuristic: bool = False
    raw_analysis: Optional[object] = None
    created_at: Optional[datetime] = None


class RunCitationInfo(BaseModel):
    id: int
    url: Optional[str] = None
    domain: Optional[str] = None
    title: Optional[str] = None
    cited_text: Optional[str] = None
    supports_brand: Optional[bool] = None
    source_type: str


class RunCompetitorInfo(BaseModel):
    id: int
    name: str
    position: Optional[int] = None
    recommendation_score: Optional[int] = None


class RunDetailResponse(BaseModel):
    run: ResearchRunDetail
    prompt: RunPromptInfo
    analysis: Optional[RunAnalysisInfo] = None
    citations: List[RunCitationInfo] = Field(default_factory=list)
    competitors: List[RunCompetitorInfo] = Field(default_factory=list)
