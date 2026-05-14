from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from automation.clients.parallel_research_client import ParallelResearchClient
from automation.models.prospecting import (
    ProspectContact,
    ProspectingListConfig,
    ProspectingRunSummary,
    ProspectResearchProfile,
    QualifiedProspect,
)
from automation.utils import extract_domain, normalize_email, unique_strings


ROLE_PRIORITIES = [
    ("founder", 10),
    ("managing partner", 15),
    ("partner", 20),
    ("principal", 30),
    ("managing director", 35),
    ("director", 45),
    ("manager", 55),
    ("chief technology officer", 60),
    ("cto", 60),
    ("head of technology", 65),
    ("technology lead", 70),
]


def default_prospecting_lists() -> list[ProspectingListConfig]:
    return [
        ProspectingListConfig(
            name="placement_agents_europe_london",
            display_name="Placement agents in Europe including London",
            geography="Europe, explicitly including London and the United Kingdom",
            target_count=20,
            candidate_pool=60,
        ),
        ProspectingListConfig(
            name="placement_agents_ny",
            display_name="Placement agents in New York",
            geography="New York City or New York State, United States",
            target_count=20,
            candidate_pool=60,
        ),
    ]


class ProspectingWorkflowService:
    def __init__(self, *, research_client: ParallelResearchClient) -> None:
        self.research_client = research_client

    def run_review(
        self,
        *,
        configs: list[ProspectingListConfig],
        output_dir: str | Path,
        generator: str = "preview",
        max_reviewed_per_list: int | None = None,
        resume: bool = False,
    ) -> list[ProspectingRunSummary]:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        summaries: list[ProspectingRunSummary] = []
        for config in configs:
            reviewed, candidate_count = self.build_list(
                config=config,
                generator=generator,
                max_reviewed=max_reviewed_per_list,
                output_dir=target_dir,
                resume=resume,
            )
            summaries.append(
                self.write_review(
                    config=config,
                    prospects=reviewed,
                    output_dir=target_dir,
                    candidate_count=candidate_count,
                )
            )
        return summaries

    def build_list(
        self,
        *,
        config: ProspectingListConfig,
        generator: str,
        max_reviewed: int | None = None,
        output_dir: Path,
        resume: bool = False,
    ) -> tuple[list[QualifiedProspect], int]:
        candidates_path = output_dir / f"{config.name}_candidates.json"
        partial_jsonl_path = output_dir / f"{config.name}_review_partial.jsonl"
        review_json_path = output_dir / f"{config.name}_review.json"
        review_csv_path = output_dir / f"{config.name}_review.csv"

        if resume and candidates_path.exists():
            candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
            print(f"[{config.name}] loaded {len(candidates)} checkpointed candidates", file=sys.stderr, flush=True)
        else:
            if not resume:
                for stale_path in (candidates_path, partial_jsonl_path, review_json_path, review_csv_path):
                    if stale_path.exists():
                        stale_path.unlink()
            print(f"[{config.name}] discovering candidates", file=sys.stderr, flush=True)
            candidates = self.discover_candidates(config=config, generator=generator)
            candidates_path.write_text(json.dumps(candidates, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            print(f"[{config.name}] saved candidates: {candidates_path}", file=sys.stderr, flush=True)

        print(f"[{config.name}] discovered {len(candidates)} candidates", file=sys.stderr, flush=True)
        reviewed = self._load_review_checkpoint(review_json_path) if resume else []
        seen_keys: set[str] = set()
        seen_names: set[str] = set()
        for prospect in reviewed:
            self._mark_seen(
                prospect.profile.company_name,
                prospect.profile.candidate_url or prospect.profile.website,
                seen_keys,
                seen_names,
            )
        qualified_count = sum(1 for prospect in reviewed if prospect.qualified)
        if reviewed:
            print(f"[{config.name}] resuming from {len(reviewed)} reviewed candidates", file=sys.stderr, flush=True)

        for candidate in candidates:
            name = (candidate.get("name") or "").strip()
            url = (candidate.get("url") or "").strip()
            if not name or self._already_seen(name, url, seen_keys, seen_names):
                continue
            skip_reason = self._candidate_prefilter_rejection(config=config, candidate=candidate)
            if skip_reason:
                self._mark_seen(name, url, seen_keys, seen_names)
                profile = self._prefilter_rejected_profile(candidate=candidate, reason=skip_reason)
                qualified = QualifiedProspect(
                    list_name=config.name,
                    qualified=False,
                    rejection_reasons=[skip_reason],
                    qualification_score=0,
                    profile=profile,
                    primary_contact=None,
                    backup_contacts=[],
                )
                reviewed.append(qualified)
                print(f"[{config.name}] skipped {name}: {skip_reason}", file=sys.stderr, flush=True)
                self._append_review_checkpoint(partial_jsonl_path, qualified)
                self.write_review(
                    config=config,
                    prospects=reviewed,
                    output_dir=output_dir,
                    candidate_count=len(candidates),
                )
                if max_reviewed is not None and len(reviewed) >= max_reviewed:
                    break
                continue
            if max_reviewed is not None and len(reviewed) >= max_reviewed:
                break
            self._mark_seen(name, url, seen_keys, seen_names)

            print(
                f"[{config.name}] researching {len(reviewed) + 1}: {name}",
                file=sys.stderr,
                flush=True,
            )
            profile = self.research_candidate(config=config, candidate=candidate)
            qualified = self.qualify_profile(config=config, profile=profile)
            reviewed.append(qualified)
            if qualified.qualified:
                qualified_count += 1
                print(
                    f"[{config.name}] qualified {qualified_count}/{config.target_count}: {profile.company_name}",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(
                    f"[{config.name}] rejected {profile.company_name}: {', '.join(qualified.rejection_reasons)}",
                    file=sys.stderr,
                    flush=True,
                )
            self._append_review_checkpoint(partial_jsonl_path, qualified)
            self.write_review(
                config=config,
                prospects=reviewed,
                output_dir=output_dir,
                candidate_count=len(candidates),
            )
            if qualified_count >= config.target_count:
                break

        return reviewed, len(candidates)

    def discover_candidates(self, *, config: ProspectingListConfig, generator: str) -> list[dict[str, Any]]:
        objective = self._discovery_objective(config)
        conditions = [
            {
                "name": "placement_agent_check",
                "description": (
                    "Company must be a placement agent, fund placement agent, fundraising advisor, "
                    "third-party marketer, or private-placement advisory firm that helps private funds, "
                    "GPs, or sponsors raise capital. The public profile must include an explicit signal "
                    "such as placement agent, fund placement, private placement, third-party fund marketer, "
                    "fund marketing, private funds placement, or capital raising in private-fund/LP/GP context. "
                    "Exclude firms whose primary business is investing their own capital, managing assets, "
                    "venture capital, private equity investing, wealth management, recruitment, or general M&A advisory."
                ),
            },
            {
                "name": "geography_check",
                "description": f"Company must have a meaningful operating presence in {config.geography}.",
            },
            {
                "name": "boutique_headcount_check",
                "description": (
                    f"Company must be boutique with no more than {config.max_headcount} people. "
                    "Prefer public evidence such as LinkedIn company size, team page count, or directory profile."
                ),
            },
            {
                "name": "active_reachable_check",
                "description": "Company must appear active and have an official website or reliable public profile.",
            },
        ]
        try:
            return self.research_client.findall_run(
                objective=objective,
                match_conditions=conditions,
                match_limit=config.candidate_pool,
                generator=generator,
                metadata={"mode": "prospecting_review", "list_name": config.name},
            )
        except Exception:
            return self.research_client.findall_candidates(
                objective=objective,
                match_limit=config.candidate_pool,
            )

    def research_candidate(self, *, config: ProspectingListConfig, candidate: dict[str, Any]) -> ProspectResearchProfile:
        name = candidate.get("name") or "Unknown company"
        candidate_url = candidate.get("url")
        candidate_website = self._candidate_website_url(candidate)
        website_domain = extract_domain(candidate_website)
        search_queries = [
            f"{name} official website placement agent team",
            f"{name} LinkedIn company 2-10 employees placement agent",
            f"{name} partner principal managing director email LinkedIn",
            f"{name} contact email partner principal LinkedIn",
        ]
        if website_domain:
            search_queries.extend(
                [
                    f"site:{website_domain} {name} team partner principal email",
                    f"site:{website_domain} {name} placement agent fundraising contact",
                ]
            )
        search = self.research_client.search(
            objective=(
                f"Find primary-source evidence that {name} is a boutique placement agent in {config.geography}; "
                f"find headcount <= {config.max_headcount}; find decision makers, principals, managers, "
                "or technology leaders with both email and LinkedIn URLs. Prefer the official website over "
                "third-party profile pages when both are available."
            ),
            queries=search_queries,
        )
        compact_search = self._compact_search(search)
        urls = self._candidate_urls(candidate_website or candidate_url, compact_search)
        extract = self.research_client.extract(
            urls=urls,
            objective=(
                "Extract only evidence relevant to prospect qualification: firm type, placement-agent/fundraising "
                f"services, offices or geography in {config.geography}, team size/headcount <= {config.max_headcount}, "
                "active status, and named decision makers/Principals/Managers/technology leaders with emails and LinkedIn URLs."
            ),
            session_id=search.get("session_id"),
        )
        prompt = self._research_prompt(
            config=config,
            candidate=candidate,
            search=compact_search,
            extract=self._compact_extract(extract),
        )
        profile = self.research_client.synthesize_structured(
            prompt=prompt,
            output_model=ProspectResearchProfile,
            metadata={"mode": "prospect_research", "list_name": config.name, "company_name": name},
        )
        assert isinstance(profile, ProspectResearchProfile)
        if not profile.company_name:
            profile.company_name = name
        profile.candidate_name = name
        profile.candidate_url = candidate_url
        if not profile.website:
            profile.website = candidate_website or candidate_url
        profile.source_urls = unique_strings([candidate_url, candidate_website, *profile.source_urls, *urls])
        profile.contacts = self._rank_contacts(profile.contacts)
        return profile

    def qualify_profile(
        self,
        *,
        config: ProspectingListConfig,
        profile: ProspectResearchProfile,
    ) -> QualifiedProspect:
        rejection_reasons: list[str] = []
        if profile.candidate_name and not self._company_names_match(profile.company_name, profile.candidate_name):
            rejection_reasons.append("candidate_identity_mismatch")
        if profile.is_placement_agent is not True:
            rejection_reasons.append("not_verified_placement_agent")
        if profile.is_boutique is not True:
            rejection_reasons.append("not_verified_boutique")
        if profile.is_active is False:
            rejection_reasons.append("inactive_or_closed")
        if profile.headcount_estimate is not None and profile.headcount_estimate > config.max_headcount:
            rejection_reasons.append("headcount_above_limit")
        if not (profile.geography or profile.geography_evidence.value):
            rejection_reasons.append("missing_geography_evidence")

        eligible_contacts = [
            contact
            for contact in self._rank_contacts(profile.contacts)
            if self._contact_is_complete(contact, config=config)
        ]
        if not eligible_contacts:
            required_fields = []
            if config.require_contact_email:
                required_fields.append("email")
            if config.require_contact_linkedin:
                required_fields.append("linkedin")
            rejection_reasons.append(f"missing_complete_contact_with_{'_and_'.join(required_fields)}")

        score = self._qualification_score(profile=profile, has_complete_contact=bool(eligible_contacts))
        return QualifiedProspect(
            list_name=config.name,
            qualified=not rejection_reasons,
            rejection_reasons=rejection_reasons,
            qualification_score=score,
            profile=profile,
            primary_contact=eligible_contacts[0] if eligible_contacts else None,
            backup_contacts=eligible_contacts[1:3],
        )

    def write_review(
        self,
        *,
        config: ProspectingListConfig,
        prospects: list[QualifiedProspect],
        output_dir: Path,
        candidate_count: int | None = None,
    ) -> ProspectingRunSummary:
        json_path = output_dir / f"{config.name}_review.json"
        csv_path = output_dir / f"{config.name}_review.csv"
        payload = [prospect.model_dump() for prospect in prospects]
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

        fieldnames = [
            "qualified",
            "rejection_reasons",
            "qualification_score",
            "account_name",
            "website",
            "linkedin_company_url",
            "firm_type",
            "geography",
            "headcount_estimate",
            "headcount_band",
            "primary_contact_name",
            "primary_contact_title",
            "primary_contact_email",
            "primary_contact_linkedin",
            "placement_agent_evidence",
            "geography_evidence",
            "headcount_evidence",
            "source_urls",
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for prospect in prospects:
                profile = prospect.profile
                contact = prospect.primary_contact or ProspectContact()
                writer.writerow(
                    {
                        "qualified": prospect.qualified,
                        "rejection_reasons": "; ".join(prospect.rejection_reasons),
                        "qualification_score": prospect.qualification_score,
                        "account_name": profile.company_name,
                        "website": profile.website or "",
                        "linkedin_company_url": profile.linkedin_company_url or "",
                        "firm_type": profile.firm_type or "",
                        "geography": profile.geography or "",
                        "headcount_estimate": profile.headcount_estimate or "",
                        "headcount_band": profile.headcount_band or "",
                        "primary_contact_name": contact.full_name or "",
                        "primary_contact_title": contact.title or "",
                        "primary_contact_email": contact.email or "",
                        "primary_contact_linkedin": contact.linkedin_url or "",
                        "placement_agent_evidence": profile.placement_agent_evidence.reasoning or "",
                        "geography_evidence": profile.geography_evidence.reasoning or "",
                        "headcount_evidence": profile.headcount_evidence.reasoning or "",
                        "source_urls": "; ".join(profile.source_urls),
                    }
                )

        qualified_count = sum(1 for prospect in prospects if prospect.qualified)
        return ProspectingRunSummary(
            list_name=config.name,
            display_name=config.display_name,
            target_count=config.target_count,
            generated_candidates=candidate_count if candidate_count is not None else len(prospects),
            reviewed_candidates=len(prospects),
            qualified_count=qualified_count,
            exported_count=min(qualified_count, config.target_count),
            output_csv=str(csv_path),
            output_json=str(json_path),
        )

    def _discovery_objective(self, config: ProspectingListConfig) -> str:
        return (
            f"FindAll boutique placement agents in {config.geography}. "
            f"Only include firms with no more than {config.max_headcount} people. "
            "They must explicitly help private funds, GPs, or sponsors raise third-party capital through fund placement, "
            "private placement, third-party fund marketing, private funds placement, or fund distribution work. "
            "Do not include a firm just because it says financial advisory, investment management, funding, "
            "financing, investor relations, or capital raising without private-fund/LP/GP context. "
            "Exclude venture capital firms, private equity investors, investment managers, asset managers, "
            "wealth managers, family offices, recruiters, executive search firms, and general M&A advisors "
            "unless their public materials explicitly say they provide fund placement or capital raising services. "
            "Prefer active firms with official websites and return the official website URL when known. "
            "The final list must support decision-maker outreach to founders, partners, principals, managers, "
            "or technology leaders where possible."
        )

    def _research_prompt(
        self,
        *,
        config: ProspectingListConfig,
        candidate: dict[str, Any],
        search: dict[str, Any],
        extract: dict[str, Any],
    ) -> str:
        return f"""
You are qualifying a prospect for a sales prospecting list.

List:
- name: {config.name}
- geography: {config.geography}
- max headcount: {config.max_headcount}
- required firm type: boutique placement agent / fund placement agent / fundraising advisor / private capital advisory
- required contact fields: email={config.require_contact_email}, linkedin={config.require_contact_linkedin}

Rules:
- Return a profile for the candidate company only.
- Set company_name to the exact candidate name unless the official site proves a minor legal-name variant.
- Do not return a market map, list, bundle, or alternative company.
- If the candidate itself does not match the ICP, keep company_name as the candidate and set the relevant booleans to false.
- Be conservative. If evidence is weak, set booleans to false or null and explain why.
- Do not infer headcount above/below the limit without evidence.
- Prefer official website, team page, LinkedIn company page, regulator/directory pages, and credible news.
- Contact candidates must be real people. Generic inboxes are not decision makers.
- Include decision makers, Principals, Managers, or technology leaders if present.
- For each contact, include email and LinkedIn only when supported by public evidence.
- Assign role_priority where lower is better: Founder/Managing Partner/Partner=10-20, Principal=30, Managing Director/Director=35-45, Manager=55, tech leader=60-70.

Candidate:
{json.dumps(candidate, ensure_ascii=True, indent=2)}

Search evidence:
{json.dumps(search, ensure_ascii=True, indent=2)[:24000]}

Extracted page evidence:
{json.dumps(extract, ensure_ascii=True, indent=2)[:32000]}
        """.strip()

    def _candidate_urls(self, candidate_url: str | None, search: dict[str, Any]) -> list[str]:
        urls = [candidate_url]
        for result in search.get("results") or []:
            url = result.get("url")
            if not url:
                continue
            urls.append(url)
        return unique_strings(urls)[:10]

    def _candidate_website_url(self, candidate: dict[str, Any]) -> str | None:
        for key in ("website", "website_url", "homepage_url"):
            value = candidate.get(key)
            if value:
                return str(value).strip()
        description = str(candidate.get("description") or "")
        match = re.search(r"\bWebsite Url:\s*(https?://[^\s|]+)", description, flags=re.IGNORECASE)
        if match:
            return match.group(1).rstrip(".,;")
        url = str(candidate.get("url") or "").strip()
        domain = extract_domain(url)
        if domain and not domain.endswith("linkedin.com"):
            return url
        return None

    def _compact_search(self, search: dict[str, Any]) -> dict[str, Any]:
        return {
            "search_id": search.get("search_id"),
            "session_id": search.get("session_id"),
            "results": [
                {
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "excerpts": self._truncate_list(result.get("excerpts") or [], limit=2, chars=700),
                }
                for result in (search.get("results") or [])[:8]
            ],
        }

    def _compact_extract(self, extract: dict[str, Any]) -> dict[str, Any]:
        return {
            "results": [
                {
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "excerpts": self._truncate_list(result.get("excerpts") or [], limit=3, chars=900),
                }
                for result in (extract.get("results") or [])[:8]
            ],
            "errors": [
                {
                    "url": error.get("url"),
                    "message": error.get("message") or error.get("error"),
                }
                for error in (extract.get("errors") or [])[:3]
            ],
        }

    def _truncate_list(self, values: list[str], *, limit: int, chars: int) -> list[str]:
        return [value[:chars] for value in values[:limit] if value]

    def _candidate_prefilter_rejection(
        self,
        *,
        config: ProspectingListConfig,
        candidate: dict[str, Any],
    ) -> str | None:
        text = " ".join(
            str(candidate.get(key) or "")
            for key in ("name", "description", "url")
        ).lower()
        strong_match = self._keyword_match(text, config.required_keywords)
        contextual_match = self._contextual_placement_signal_match(text, config)
        excluded_match = self._keyword_match(text, config.excluded_keywords)
        if excluded_match and not strong_match:
            return f"prefilter_excluded_keyword:{excluded_match}"
        if not strong_match and not contextual_match:
            return "prefilter_missing_placement_agent_signal"
        return None

    def _keyword_match(self, text: str, keywords: list[str]) -> str | None:
        for keyword in keywords:
            pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
            if re.search(pattern, text):
                return keyword
        return None

    def _contextual_placement_signal_match(self, text: str, config: ProspectingListConfig) -> str | None:
        contextual_match = self._keyword_match(text, config.contextual_keywords)
        context_match = self._keyword_match(text, config.context_keywords)
        if contextual_match and context_match:
            return contextual_match
        return None

    def _prefilter_rejected_profile(self, *, candidate: dict[str, Any], reason: str) -> ProspectResearchProfile:
        name = candidate.get("name") or "Unknown company"
        url = candidate.get("url")
        return ProspectResearchProfile(
            candidate_name=name,
            candidate_url=url,
            company_name=name,
            website=url,
            is_placement_agent=False,
            is_boutique=None,
            is_active=None,
            source_urls=unique_strings([url]),
            placement_agent_evidence={
                "value": None,
                "reasoning": f"Skipped before paid research: {reason}",
                "confidence": "low",
                "citations": [],
            },
        )

    def _load_review_checkpoint(self, review_json_path: Path) -> list[QualifiedProspect]:
        if not review_json_path.exists():
            return []
        payload = json.loads(review_json_path.read_text(encoding="utf-8"))
        return [QualifiedProspect.model_validate(item) for item in payload]

    def _append_review_checkpoint(self, partial_jsonl_path: Path, prospect: QualifiedProspect) -> None:
        with partial_jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(prospect.model_dump(), ensure_ascii=True) + "\n")

    def _already_seen(
        self,
        name: str,
        url: str | None,
        seen_keys: set[str],
        seen_names: set[str],
    ) -> bool:
        key = self._candidate_identity_key(url)
        name_key = re.sub(r"\W+", " ", name.lower()).strip()
        dedupe_key = key or name_key
        return bool(dedupe_key in seen_keys or name_key in seen_names)

    def _mark_seen(
        self,
        name: str,
        url: str | None,
        seen_keys: set[str],
        seen_names: set[str],
    ) -> None:
        key = self._candidate_identity_key(url)
        name_key = re.sub(r"\W+", " ", name.lower()).strip()
        dedupe_key = key or name_key
        if dedupe_key:
            seen_keys.add(dedupe_key)
        if name_key:
            seen_names.add(name_key)

    def _candidate_identity_key(self, url: str | None) -> str:
        domain = extract_domain(url) or ""
        if not url:
            return domain
        parsed_url = url if "://" in url else f"https://{url}"
        parsed = urlparse(parsed_url)
        host = parsed.netloc.lower().removeprefix("www.")
        path = re.sub(r"/+", "/", parsed.path.lower()).strip("/")
        if host.endswith("linkedin.com") and path:
            return f"{host}/{path}"
        return domain

    def _company_names_match(self, returned_name: str | None, candidate_name: str | None) -> bool:
        returned = self._name_tokens(returned_name)
        candidate = self._name_tokens(candidate_name)
        if not returned or not candidate:
            return False
        if returned == candidate:
            return True
        return candidate.issubset(returned) or returned.issubset(candidate)

    def _name_tokens(self, value: str | None) -> set[str]:
        stopwords = {
            "a",
            "advisers",
            "advisors",
            "capital",
            "company",
            "group",
            "inc",
            "limited",
            "llc",
            "llp",
            "ltd",
            "management",
            "partners",
            "the",
        }
        normalized = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
        return {token for token in normalized.split() if token and token not in stopwords}

    def _rank_contacts(self, contacts: list[ProspectContact]) -> list[ProspectContact]:
        ranked: list[ProspectContact] = []
        for contact in contacts:
            contact.email = normalize_email(contact.email)
            contact.role_priority = min(contact.role_priority or 100, self._role_priority(contact.title))
            ranked.append(contact)
        return sorted(
            ranked,
            key=lambda contact: (
                contact.role_priority,
                0 if contact.email else 1,
                0 if contact.linkedin_url else 1,
                contact.full_name or "",
            ),
        )

    def _role_priority(self, title: str | None) -> int:
        lowered = (title or "").lower()
        for keyword, priority in ROLE_PRIORITIES:
            if keyword in lowered:
                return priority
        return 100

    def _contact_is_complete(self, contact: ProspectContact, *, config: ProspectingListConfig) -> bool:
        if config.require_contact_email and not contact.email:
            return False
        if config.require_contact_linkedin and not contact.linkedin_url:
            return False
        return bool(contact.full_name or contact.email or contact.linkedin_url)

    def _qualification_score(self, *, profile: ProspectResearchProfile, has_complete_contact: bool) -> int:
        score = 0
        if profile.is_placement_agent is True:
            score += 30
        if profile.is_boutique is True:
            score += 25
        if profile.geography or profile.geography_evidence.value:
            score += 15
        if profile.is_active is not False:
            score += 10
        if has_complete_contact:
            score += 20
        return score


def load_prospecting_configs(path: str | Path | None) -> list[ProspectingListConfig]:
    if path is None:
        return default_prospecting_lists()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("lists", [])
    return [ProspectingListConfig.model_validate(item) for item in payload]
