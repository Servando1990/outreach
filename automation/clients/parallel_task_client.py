from __future__ import annotations

import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from automation.config import Settings
from automation.models.prospect import DiscoveryResults, ProspectProfile

ModelT = TypeVar("ModelT", bound=BaseModel)


class ParallelTaskClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        self.settings.require_parallel()
        return {
            "Content-Type": "application/json",
            "x-api-key": self.settings.parallel_api_key or "",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        with httpx.Client(timeout=self.settings.parallel_timeout_seconds) as client:
            response = client.request(
                method,
                f"{self.settings.parallel_base_url}{path}",
                headers=self._headers(),
                **kwargs,
            )
            response.raise_for_status()
            return response.json()

    def create_run(
        self,
        *,
        input_data: str,
        output_schema: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        webhook: dict[str, Any] | None = None,
        processor: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "input": input_data,
            "processor": processor or self.settings.parallel_processor,
            "task_spec": {
                "output_schema": {
                    "type": "json",
                    "json_schema": output_schema,
                }
            },
            "metadata": metadata or {},
        }
        if webhook:
            payload["webhook"] = webhook
        return self._request("POST", "/v1/tasks/runs", json=payload)

    def get_result(self, run_id: str) -> dict[str, Any]:
        deadline = time.time() + self.settings.parallel_result_timeout_seconds
        last_status = "running"
        while time.time() < deadline:
            result = self._request("GET", f"/v1/tasks/runs/{run_id}/result")
            output = result.get("output")
            if output:
                return result

            run_data = result.get("run") or result.get("data") or {}
            last_status = run_data.get("status", last_status)
            if last_status in {"failed", "canceled"}:
                raise RuntimeError(f"Parallel task run {run_id} ended with status={last_status}.")
            time.sleep(self.settings.parallel_poll_interval_seconds)

        raise TimeoutError(f"Timed out waiting for Parallel task result for run_id={run_id}.")

    def run_structured(
        self,
        *,
        input_data: str,
        output_model: type[ModelT],
        metadata: dict[str, Any] | None = None,
        webhook: dict[str, Any] | None = None,
    ) -> tuple[ModelT, dict[str, Any]]:
        run = self.create_run(
            input_data=input_data,
            output_schema=output_model.model_json_schema(),
            metadata=metadata,
            webhook=webhook,
        )
        run_id = run.get("run_id") or run.get("run", {}).get("run_id")
        if not run_id:
            raise RuntimeError("Parallel create_run did not return a run_id.")
        result = self.get_result(run_id)
        output = result.get("output") or {}
        content = output.get("content")
        if content is None:
            raise RuntimeError(f"Parallel task run {run_id} returned no structured content.")
        return output_model.model_validate(content), result

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
