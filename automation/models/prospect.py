from __future__ import annotations

from pydantic import BaseModel, Field


class DecisionMaker(BaseModel):
    full_name: str | None = None
    title: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    profile_photo_url: str | None = None
    confidence: float | None = None
    source_urls: list[str] = Field(default_factory=list)


class DiscoveryCandidate(BaseModel):
    company_name: str
    website: str | None = None
    linkedin_company_url: str | None = None
    firm_type: str | None = None
    why_it_matches: str


class DiscoveryResults(BaseModel):
    companies: list[DiscoveryCandidate] = Field(default_factory=list)


class ProspectProfile(BaseModel):
    company_name: str
    normalized_company_name: str | None = None
    website: str | None = None
    linkedin_company_url: str | None = None
    firm_type: str | None = None
    geography: str | None = None
    outbound_need_summary: str | None = None
    outbound_need_level: str | None = None
    recent_trigger_summary: str | None = None
    recent_trigger_date: str | None = None
    recent_signal_level: str | None = None
    data_confidence_level: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    decision_makers: list[DecisionMaker] = Field(default_factory=list)
    prompt_version: str | None = None

    firm_fit_score: int | None = None
    signal_score: int | None = None
    contact_coverage_score: int | None = None
    confidence_score: int | None = None
    outbound_fit_score: int | None = None
    outbound_fit_bucket: str | None = None
    outbound_fit_reason: str | None = None
