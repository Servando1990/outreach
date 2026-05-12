from __future__ import annotations

import time
from typing import Any

from parallel import Parallel
from pydantic import BaseModel

from automation.config import Settings


FINDALL_BETA = "findall-2025-09-15"


class ParallelResearchClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.require_parallel()
        self.client = Parallel(
            api_key=self.settings.parallel_api_key,
            base_url=self.settings.parallel_base_url,
            timeout=self.settings.parallel_timeout_seconds,
        )

    def search(
        self,
        *,
        objective: str,
        queries: list[str],
        max_chars_total: int = 12000,
    ) -> dict[str, Any]:
        result = self.client.search(
            search_queries=queries,
            objective=objective,
            max_chars_total=max_chars_total,
            mode="advanced",
        )
        return result.to_dict()

    def extract(
        self,
        *,
        urls: list[str],
        objective: str,
        session_id: str | None = None,
        max_chars_total: int = 16000,
    ) -> dict[str, Any]:
        if not urls:
            return {"results": [], "errors": []}
        result = self.client.extract(
            urls=urls[:10],
            objective=objective,
            session_id=session_id,
            max_chars_total=max_chars_total,
        )
        return result.to_dict()

    def findall_candidates(
        self,
        *,
        objective: str,
        match_limit: int,
    ) -> list[dict[str, Any]]:
        result = self.client.beta.findall.candidates(
            entity_type="company",
            objective=objective,
            match_limit=match_limit,
        )
        return result.to_dict().get("candidates") or []

    def findall_run(
        self,
        *,
        objective: str,
        match_conditions: list[dict[str, str]],
        match_limit: int,
        generator: str,
        metadata: dict[str, str | float | bool] | None = None,
    ) -> list[dict[str, Any]]:
        run = self.client.beta.findall.create(
            objective=objective,
            entity_type="companies",
            match_conditions=match_conditions,
            match_limit=max(5, match_limit),
            generator=generator,  # type: ignore[arg-type]
            metadata=metadata or {},
            betas=[FINDALL_BETA],
        )
        findall_id = run.findall_id
        deadline = time.time() + self.settings.parallel_result_timeout_seconds
        while time.time() < deadline:
            status = self.client.beta.findall.retrieve(findall_id, betas=[FINDALL_BETA])
            if not status.status.is_active:
                break
            time.sleep(self.settings.parallel_poll_interval_seconds)
        result = self.client.beta.findall.result(findall_id, betas=[FINDALL_BETA])
        payload = result.to_dict()
        return [
            candidate
            for candidate in payload.get("candidates", [])
            if candidate.get("match_status") == "matched"
        ]

    def synthesize_structured(
        self,
        *,
        prompt: str,
        output_model: type[BaseModel],
        metadata: dict[str, Any] | None = None,
    ) -> BaseModel:
        result = self.client.task_run.execute(
            input=prompt,
            processor=self.settings.parallel_processor,
            metadata=self._metadata(metadata),
            output=output_model,
            timeout=self.settings.parallel_result_timeout_seconds,
        )
        parsed = result.output.parsed
        if parsed is None:
            raise RuntimeError("Parallel task run returned no parsed structured output.")
        return parsed

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
