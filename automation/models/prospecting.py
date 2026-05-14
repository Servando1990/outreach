from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProspectingListConfig(BaseModel):
    name: str
    display_name: str
    geography: str
    target_count: int = 20
    candidate_pool: int = 60
    max_headcount: int = 10
    require_contact_email: bool = True
    require_contact_linkedin: bool = True
    required_keywords: list[str] = Field(
        default_factory=lambda: [
            "placement agent",
            "fund placement",
            "third party marketer",
            "third-party marketer",
            "third party fund marketer",
            "third-party fund marketer",
            "fund marketing",
            "private funds placement",
            "placement and advisory",
        ]
    )
    contextual_keywords: list[str] = Field(
        default_factory=lambda: [
            "fundraising",
            "capital raising",
            "distribution",
            "asset raising",
            "private placement",
            "lp fundraising",
            "investor relations",
        ]
    )
    context_keywords: list[str] = Field(
        default_factory=lambda: [
            "fund",
            "funds",
            "gp",
            "gps",
            "sponsor",
            "sponsors",
            "lp",
            "lps",
            "limited partners",
            "private markets",
            "alternative investment",
            "alternative investments",
            "alternatives sector",
        ]
    )
    excluded_keywords: list[str] = Field(
        default_factory=lambda: [
            "venture capital",
            "private equity firm",
            "private equity fund",
            "growth equity",
            "investment manager",
            "asset management",
            "asset manager",
            "wealth manager",
            "investment bank",
            "investment banking",
            "family office",
            "recruitment",
            "recruiter",
            "executive search",
            "m&a advisory",
            "mergers and acquisitions",
            "corporate finance advisory",
        ]
    )
    allowed_firm_types: list[str] = Field(
        default_factory=lambda: [
            "placement agent",
            "fund placement agent",
            "fundraising advisor",
            "private capital advisory",
            "capital raising advisor",
        ]
    )
    target_contact_titles: list[str] = Field(
        default_factory=lambda: [
            "founder",
            "managing partner",
            "partner",
            "principal",
            "managing director",
            "director",
            "manager",
            "cto",
            "chief technology officer",
            "head of technology",
            "technology lead",
        ]
    )


class ResearchCitation(BaseModel):
    title: str | None = None
    url: str
    excerpt: str | None = None


class EvidenceField(BaseModel):
    value: str | None = None
    reasoning: str | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    citations: list[ResearchCitation] = Field(default_factory=list)


class ProspectContact(BaseModel):
    full_name: str | None = None
    title: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    role_priority: int = 100
    confidence: Literal["low", "medium", "high"] | None = None
    source_urls: list[str] = Field(default_factory=list)


class ProspectResearchProfile(BaseModel):
    candidate_name: str | None = None
    candidate_url: str | None = None
    company_name: str
    website: str | None = None
    linkedin_company_url: str | None = None
    firm_type: str | None = None
    geography: str | None = None
    office_locations: list[str] = Field(default_factory=list)
    headcount_estimate: int | None = None
    headcount_band: str | None = None
    is_placement_agent: bool | None = None
    is_boutique: bool | None = None
    is_active: bool | None = None
    placement_agent_evidence: EvidenceField = Field(default_factory=EvidenceField)
    geography_evidence: EvidenceField = Field(default_factory=EvidenceField)
    headcount_evidence: EvidenceField = Field(default_factory=EvidenceField)
    active_firm_evidence: EvidenceField = Field(default_factory=EvidenceField)
    source_urls: list[str] = Field(default_factory=list)
    contacts: list[ProspectContact] = Field(default_factory=list)


class QualifiedProspect(BaseModel):
    list_name: str
    qualified: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    qualification_score: int = 0
    profile: ProspectResearchProfile
    primary_contact: ProspectContact | None = None
    backup_contacts: list[ProspectContact] = Field(default_factory=list)


class ProspectingRunSummary(BaseModel):
    list_name: str
    display_name: str
    target_count: int
    generated_candidates: int
    reviewed_candidates: int
    qualified_count: int
    exported_count: int
    output_csv: str
    output_json: str
