from __future__ import annotations

import csv
from pathlib import Path

from automation.clients.parallel_task_client import ParallelTaskClient
from automation.config import Settings
from automation.models.prospect import DiscoveryCandidate, ProspectProfile
from automation.services.scoring_service import ScoringService


class EnrichmentService:
    def __init__(
        self,
        *,
        settings: Settings,
        task_client: ParallelTaskClient,
        scoring_service: ScoringService,
    ) -> None:
        self.settings = settings
        self.task_client = task_client
        self.scoring_service = scoring_service

    def discover(self, *, query: str, limit: int) -> list[ProspectProfile]:
        discovery_results = self.task_client.discover_candidates(query=query, limit=limit)
        profiles: list[ProspectProfile] = []
        for candidate in discovery_results.companies[:limit]:
            profiles.append(self.enrich_candidate(candidate))
        return profiles

    def enrich_candidate(
        self,
        candidate: DiscoveryCandidate,
        *,
        signal_context: str | None = None,
    ) -> ProspectProfile:
        profile = self.task_client.enrich_company(
            company_name=candidate.company_name,
            website=candidate.website,
            query_context=candidate.why_it_matches,
            signal_context=signal_context,
        )
        if not profile.firm_type and candidate.firm_type:
            profile.firm_type = candidate.firm_type
        return self.scoring_service.score(profile)

    def enrich_company(
        self,
        *,
        company_name: str,
        website: str | None = None,
        signal_context: str | None = None,
    ) -> ProspectProfile:
        profile = self.task_client.enrich_company(
            company_name=company_name,
            website=website,
            signal_context=signal_context,
        )
        return self.scoring_service.score(profile)

    def backfill_from_csv(self, *, csv_path: str | Path, limit: int | None = None) -> list[ProspectProfile]:
        rows = self._read_csv_rows(csv_path)
        profiles: list[ProspectProfile] = []
        for index, row in enumerate(rows):
            if limit is not None and index >= limit:
                break
            company_name = row.get("Account name") or row.get("company_name") or row.get("Company")
            website = row.get("Account website") or row.get("website") or row.get("Website")
            if not company_name:
                continue
            profiles.append(
                self.enrich_company(
                    company_name=company_name,
                    website=website,
                )
            )
        return profiles

    def _read_csv_rows(self, csv_path: str | Path) -> list[dict[str, str]]:
        path = Path(csv_path)
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
