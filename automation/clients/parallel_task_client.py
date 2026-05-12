from __future__ import annotations

from typing import Any, TypeVar

from parallel import Parallel
from pydantic import BaseModel

from automation.config import Settings
from automation.models.prospect import DiscoveryResults, ProspectProfile

ModelT = TypeVar("ModelT", bound=BaseModel)


class ParallelTaskClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.require_parallel()
        self.client = Parallel(
            api_key=self.settings.parallel_api_key,
            base_url=self.settings.parallel_base_url,
            timeout=self.settings.parallel_timeout_seconds,
        )

    def run_structured(
        self,
        *,
        input_data: str,
        output_model: type[ModelT],
        metadata: dict[str, Any] | None = None,
    ) -> tuple[ModelT, dict[str, Any]]:
        result = self.client.task_run.execute(
            input=input_data,
            processor=self.settings.parallel_processor,
            metadata=self._metadata(metadata),
            output=output_model,
            timeout=self.settings.parallel_result_timeout_seconds,
        )
        parsed = result.output.parsed
        if parsed is None:
            raise RuntimeError("Parallel task run returned no parsed structured output.")
        return parsed, result.to_dict()

    def _metadata(self, metadata: dict[str, Any] | None) -> dict[str, str | float | bool]:
        normalized: dict[str, str | float | bool] = {}
        for key, value in (metadata or {}).items():
            if value is None:
                continue
            if isinstance(value, bool | float):
                normalized[key] = value
            elif isinstance(value, int):
                normalized[key] = float(value)
            else:
                normalized[key] = str(value)[:512]
        return normalized

    def discover_candidates(self, *, query: str, limit: int) -> DiscoveryResults:
        prompt = f"""
You are discovering CRM prospects for an outbound automation agency.

Ideal accounts:
- {self.settings.icp_description}

Task:
- Find up to {limit} firms that best match the search query below.
- Favor firms that are currently active, reachable, and likely to benefit from outbound prospecting or lead generation help.
- Return compact reasons, not essays.
- Prefer official websites and strong public identifiers.

Search query:
{query}
        """.strip()

        result, _ = self.run_structured(
            input_data=prompt,
            output_model=DiscoveryResults,
            metadata={
                "mode": "discover",
                "prompt_version": self.settings.prompt_version,
                "query": query,
            },
        )
        return result

    def enrich_company(
        self,
        *,
        company_name: str,
        website: str | None = None,
        query_context: str | None = None,
        signal_context: str | None = None,
    ) -> ProspectProfile:
        prompt = f"""
You are enriching CRM prospects for an outbound automation agency.

Ideal accounts:
- {self.settings.icp_description}

Research this company and return a structured profile with:
- company identity
- firm type
- why they likely do or do not need outbound prospecting / CRM enrichment support
- recent trigger summary
- likely decision-makers such as founders, partners, managing directors, or GTM leaders
- high-quality source URLs

Rules:
- Be conservative. Leave fields null when confidence is low.
- Only include decision-makers that appear public and relevant.
- Prefer work email addresses when strongly supported; otherwise leave email empty.
- Use low, medium, or high for outbound_need_level, recent_signal_level, and data_confidence_level.
- Set prompt_version to "{self.settings.prompt_version}".

Company:
- name: {company_name}
- website: {website or "unknown"}
- discovery context: {query_context or "none"}
- signal context: {signal_context or "none"}
        """.strip()

        profile, _ = self.run_structured(
            input_data=prompt,
            output_model=ProspectProfile,
            metadata={
                "mode": "enrich",
                "prompt_version": self.settings.prompt_version,
                "company_name": company_name,
                "website": website,
            },
        )
        if not profile.prompt_version:
            profile.prompt_version = self.settings.prompt_version
        if not profile.company_name:
            profile.company_name = company_name
        if not profile.website and website:
            profile.website = website
        return profile
