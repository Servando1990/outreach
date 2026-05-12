from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from parallel import Parallel


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"

DEAL_NAME = "Aggregate Trucking"
DEAL_FACTS = {
    "sales_revenue": "$31.0 million",
    "adjusted_ebitda": "$3.4 million",
    "location": "Northern US",
}

OBJECTIVE = """
FindAll buyer organizations, not trucking operators.

Find private equity firms, independent sponsors, family offices, and PE-backed platform companies that are plausible acquirers for a lower-middle-market industrial services company with $31.0 million of revenue, $3.4 million of adjusted EBITDA, and operations in the Northern US.

The target company is an aggregate trucking business. Prioritize buyer organizations with public portfolio exposure, acquisition criteria, add-on strategy, or acquisition history in transportation and logistics, construction materials, aggregates, heavy civil infrastructure services, dump truck fleets, fleet services, waste hauling, industrial transportation, commercial vehicle services, or route-based industrial services.

Do not return standalone trucking companies, freight carriers, or local operators unless there is public evidence that they are PE-backed, acquisitive, and could be a platform or strategic add-on buyer. The candidate entity should usually be the financial sponsor or acquisitive platform company, not a company merely similar to the target.
""".strip()

MATCH_CONDITIONS: list[dict[str, str]] = [
    {
        "name": "buyer_type_fit",
        "description": (
            "Candidate must be a private equity firm, independent sponsor, family office with "
            "direct private-company acquisitions, or a PE-backed platform company that could "
            "reasonably acquire lower-middle-market businesses. Do not match standalone "
            "trucking operators, freight carriers, or local industrial companies unless public "
            "evidence shows they are PE-backed, an investment sponsor, or explicitly acquisitive. "
            "Do not classify a truck broker, carrier, truck rental company, consultant, or "
            "LinkedIn-only operating business as an independent sponsor unless it publicly "
            "states that it acquires companies or invests sponsor equity."
        ),
    },
    {
        "name": "acquisition_authority_fit",
        "description": (
            "Candidate must have public evidence that it can execute acquisitions: investment "
            "criteria, add-on program, prior acquisitions as buyer, private equity backing, "
            "corporate development activity, or sponsor/family-office capital. Do not match "
            "businesses that merely operate in trucking/logistics without evidence of acquisition "
            "authority or an acquisition mandate."
        ),
    },
    {
        "name": "sector_thesis_fit",
        "description": (
            "Candidate must show public portfolio exposure, acquisition history, or stated "
            "investment interest in aggregates, construction materials, trucking/logistics, "
            "dump truck fleets, infrastructure services, waste hauling, fleet services, "
            "commercial vehicle services, or route-based industrial services."
        ),
    },
    {
        "name": "lower_middle_market_or_addon_fit",
        "description": (
            "Candidate must be plausible for a business with about $3.4M adjusted EBITDA. "
            "Evidence can include lower-middle-market focus, founder-owned business focus, "
            "add-on acquisition strategy, small platform acquisitions, or stated criteria "
            "overlapping roughly $2M-$10M EBITDA. If exact EBITDA criteria are not public, "
            "match candidates with clear add-on acquisition behavior in relevant sectors."
        ),
    },
    {
        "name": "geography_fit",
        "description": (
            "Candidate must invest in or operate across North America, the US, the Northern US, "
            "the Midwest, the Northeast, or nearby regions. National US buyers may match."
        ),
    },
]

CLIENT_RULE_OBJECTIVE = """
FindAll potential acquirers matching this rule-based buyer screen:

Look for trucking, logistics, transportation, fleet services, or industrial services companies in the Northeast US or broader Northern/Eastern US that are owned by private equity, backed by private equity, or controlled by a financial sponsor.

The target company is Aggregate Trucking, a Northern US aggregate trucking business with $31.0 million of revenue and $3.4 million of adjusted EBITDA. Identify PE-backed platform logistics businesses, sponsor-owned trucking/logistics platforms, or PE firms with a clearly relevant platform company that may be a fit to acquire the business.

Prioritize candidates with public evidence of private equity ownership, a logistics/transportation platform in the portfolio, add-on acquisition strategy, prior acquisitions, or corporate development activity. The output should identify the potential acquirer and, when relevant, its PE sponsor or platform company.
""".strip()

CLIENT_RULE_MATCH_CONDITIONS: list[dict[str, str]] = [
    {
        "name": "pe_ownership_or_sponsor_backing",
        "description": (
            "Candidate must have public evidence of current private equity ownership, private "
            "equity backing, financial sponsor control, or ownership by a family office / "
            "independent sponsor. If the candidate is a PE firm, it must have a relevant "
            "portfolio/platform company in trucking, logistics, or adjacent industrial services."
        ),
    },
    {
        "name": "platform_logistics_business_fit",
        "description": (
            "Candidate must be or own a platform business in trucking, logistics, transportation, "
            "fleet services, heavy civil infrastructure services, construction materials hauling, "
            "waste hauling, industrial transportation, or route-based industrial services."
        ),
    },
    {
        "name": "northeast_or_northern_us_fit",
        "description": (
            "Candidate should operate, invest, or have portfolio coverage in the Northeast US, "
            "Northern US, Eastern US, Midwest, or broader North America. Strong Northeast or "
            "Northern/Eastern US evidence is preferred but national North American platforms can match."
        ),
    },
    {
        "name": "acquisition_or_addon_strategy",
        "description": (
            "Candidate must have evidence of acquisition activity, add-on strategy, roll-up "
            "strategy, corporate development, acquisitive growth, investment criteria, or prior "
            "M&A in trucking/logistics/industrial services."
        ),
    },
    {
        "name": "aggregate_trucking_deal_fit",
        "description": (
            "Candidate must be plausible for a $31.0M revenue and $3.4M adjusted EBITDA "
            "aggregate trucking acquisition. Evidence can include lower-middle-market acquisition "
            "criteria, add-on acquisition appetite, founder-owned business focus, or a platform "
            "that could absorb a smaller add-on."
        ),
    },
]

ENRICHMENT_SCHEMA: dict[str, Any] = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "buyer_category": {
                "type": "string",
                "description": "PE firm, independent sponsor, family office, or PE-backed platform company.",
            },
            "relevant_platform_or_portfolio_company": {
                "type": "string",
                "description": "Most relevant platform or portfolio company, if any. Use an empty string if unknown.",
            },
            "acquisition_rationale": {
                "type": "string",
                "description": "Concise explanation of why this buyer may fit the Aggregate Trucking deal.",
            },
            "likely_contact_name": {
                "type": "string",
                "description": "Most relevant public individual contact for this opportunity, if supported. Empty string if unknown.",
            },
            "likely_contact_title": {
                "type": "string",
                "description": "Title of the likely contact. Empty string if unknown.",
            },
            "likely_contact_url": {
                "type": "string",
                "description": "Public URL for the likely contact or team profile. Empty string if unknown.",
            },
            "contact_page_url": {
                "type": "string",
                "description": "Official contact or investment-submission URL. Empty string if unknown.",
            },
            "contact_email": {
                "type": "string",
                "description": "Public work email only when strongly supported. Empty string if none found.",
            },
            "fit_score": {
                "type": "integer",
                "description": "Score from 1 to 5, where 5 is the strongest buyer fit.",
            },
            "next_step": {
                "type": "string",
                "description": "Recommended outreach next step in one sentence.",
            },
        },
        "required": [
            "buyer_category",
            "relevant_platform_or_portfolio_company",
            "acquisition_rationale",
            "likely_contact_name",
            "likely_contact_title",
            "likely_contact_url",
            "contact_page_url",
            "contact_email",
            "fit_score",
            "next_step",
        ],
    },
}

ENRICHMENT_FIELDS = set(ENRICHMENT_SCHEMA["json_schema"]["required"])


def main() -> int:
    args = parse_args()
    load_env_file(Path.cwd() / ".env")
    load_env_file(Path.cwd() / ".env.local")

    spec = build_findall_spec(
        generator=args.generator,
        match_limit=args.match_limit,
        search_profile=args.search_profile,
    )

    if args.dry_run:
        print(json.dumps({"findall": spec, "enrichment_schema": ENRICHMENT_SCHEMA}, indent=2))
        return 0

    api_key = os.getenv("PARALLEL_API_KEY")
    if not api_key:
        raise RuntimeError("PARALLEL_API_KEY is required. Use --dry-run to validate without making an API call.")

    client = Parallel(api_key=api_key, timeout=args.request_timeout)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Creating one FindAll run for {DEAL_NAME} with generator={args.generator}...")
    run = client.beta.findall.create(**spec)
    findall_id = run.findall_id
    print(f"FindAll run created: {findall_id}")

    if not args.no_enrich:
        print("Adding buyer/contact enrichment schema...")
        client.beta.findall.enrich(
            findall_id,
            output_schema=ENRICHMENT_SCHEMA,
            processor=args.enrichment_processor,
        )

    run = poll_until_complete(
        client=client,
        findall_id=findall_id,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
    )

    result = wait_for_result_snapshot(
        client=client,
        findall_id=findall_id,
        expect_enrichment=not args.no_enrich,
        poll_interval=args.poll_interval,
        timeout=args.enrichment_timeout,
    )
    payload = {
        "deal": {"name": DEAL_NAME, **DEAL_FACTS},
        "findall_id": findall_id,
        "run": to_dict(run),
        "result": to_dict(result),
    }
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = RESULTS_DIR / f"aggregate_trucking_{findall_id}_{timestamp}.json"
    csv_path = RESULTS_DIR / f"aggregate_trucking_{findall_id}_{timestamp}.csv"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    write_csv(csv_path, payload)

    print(f"Wrote JSON: {json_path}")
    print(f"Wrote CSV: {csv_path}")
    print_summary(payload)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate one Parallel FindAll buyer-match workflow.")
    parser.add_argument("--dry-run", action="store_true", help="Print the FindAll spec without calling Parallel.")
    parser.add_argument(
        "--generator",
        choices=["preview", "base", "core", "pro"],
        default="preview",
        help="FindAll generator. Start with preview for validation.",
    )
    parser.add_argument("--match-limit", type=int, default=5, help="Smallest API-supported value is 5.")
    parser.add_argument(
        "--search-profile",
        choices=["buyer-first", "client-rule"],
        default="buyer-first",
        help="buyer-first is broader; client-rule tests the client's PE-backed trucking/logistics platform screen.",
    )
    parser.add_argument("--no-enrich", action="store_true", help="Create the FindAll run without enrichment.")
    parser.add_argument("--enrichment-processor", default="core", help="Task processor for matched-candidate enrichment.")
    parser.add_argument("--poll-interval", type=float, default=10.0, help="Seconds between status checks.")
    parser.add_argument("--timeout", type=float, default=900.0, help="Maximum seconds to wait for completion.")
    parser.add_argument(
        "--enrichment-timeout",
        type=float,
        default=300.0,
        help="Maximum seconds to wait after matching for enrichment fields to appear.",
    )
    parser.add_argument("--request-timeout", type=float, default=120.0, help="Per-request SDK timeout in seconds.")
    return parser.parse_args()


def build_findall_spec(*, generator: str, match_limit: int, search_profile: str) -> dict[str, Any]:
    if match_limit < 5:
        raise ValueError("FindAll match_limit must be at least 5.")
    objective = OBJECTIVE
    match_conditions = MATCH_CONDITIONS
    if search_profile == "client-rule":
        objective = CLIENT_RULE_OBJECTIVE
        match_conditions = CLIENT_RULE_MATCH_CONDITIONS
    return {
        "objective": objective,
        "entity_type": "companies",
        "match_conditions": match_conditions,
        "generator": generator,
        "match_limit": match_limit,
        "metadata": {
            "experiment": "experimental-mvv",
            "search_profile": search_profile,
            "deal_name": DEAL_NAME,
            "deal_revenue": DEAL_FACTS["sales_revenue"],
            "deal_ebitda": DEAL_FACTS["adjusted_ebitda"],
            "deal_location": DEAL_FACTS["location"],
        },
    }


def poll_until_complete(
    *,
    client: Parallel,
    findall_id: str,
    poll_interval: float,
    timeout: float,
) -> Any:
    started_at = time.monotonic()
    while True:
        run = client.beta.findall.retrieve(findall_id)
        status = run.status.status
        metrics = run.status.metrics
        generated = metrics.generated_candidates_count
        matched = metrics.matched_candidates_count
        print(f"Status={status}; generated={generated}; matched={matched}")

        if not run.status.is_active:
            if status not in {"completed", "cancelled"}:
                reason = run.status.termination_reason or "unknown"
                raise RuntimeError(f"FindAll run ended with status={status}, reason={reason}.")
            return run

        if time.monotonic() - started_at > timeout:
            raise TimeoutError(f"Timed out waiting for FindAll run {findall_id}.")

        time.sleep(poll_interval)


def wait_for_result_snapshot(
    *,
    client: Parallel,
    findall_id: str,
    expect_enrichment: bool,
    poll_interval: float,
    timeout: float,
) -> Any:
    started_at = time.monotonic()
    result = client.beta.findall.result(findall_id)
    if not expect_enrichment:
        return result

    while True:
        matched = [candidate for candidate in result.candidates if candidate.match_status == "matched"]
        enriched = [candidate for candidate in matched if candidate.output and ENRICHMENT_FIELDS & set(candidate.output)]
        if matched and len(enriched) == len(matched):
            print(f"Enrichment fields present for {len(enriched)} matched candidates.")
            return result

        if time.monotonic() - started_at > timeout:
            print(
                "Enrichment fields were not present before timeout; writing the latest result snapshot. "
                "Match-condition evidence is still available."
            )
            return result

        print(f"Waiting for enrichment fields; enriched={len(enriched)} matched={len(matched)}")
        time.sleep(poll_interval)
        result = client.beta.findall.result(findall_id)


def write_csv(path: Path, payload: dict[str, Any]) -> None:
    result = payload["result"]
    candidates = result.get("candidates", [])
    fieldnames = [
        "candidate_id",
        "match_status",
        "name",
        "url",
        "description",
        "buyer_category",
        "relevant_platform_or_portfolio_company",
        "fit_score",
        "acquisition_rationale",
        "likely_contact_name",
        "likely_contact_title",
        "likely_contact_url",
        "contact_page_url",
        "contact_email",
        "next_step",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for candidate in candidates:
            output = candidate.get("output") or {}
            row = {
                "candidate_id": candidate.get("candidate_id", ""),
                "match_status": candidate.get("match_status", ""),
                "name": candidate.get("name", ""),
                "url": candidate.get("url", ""),
                "description": candidate.get("description", ""),
            }
            for key in fieldnames:
                if key not in row:
                    row[key] = stringify_field(output.get(key, ""))
            writer.writerow(row)


def print_summary(payload: dict[str, Any]) -> None:
    candidates = payload["result"].get("candidates", [])
    matched = [candidate for candidate in candidates if candidate.get("match_status") == "matched"]
    print(f"Matched candidates: {len(matched)}")
    for index, candidate in enumerate(matched[:5], start=1):
        output = candidate.get("output") or {}
        fit_score = unwrap_field(output.get("fit_score", ""))
        contact = unwrap_field(output.get("likely_contact_name")) or unwrap_field(output.get("contact_page_url", ""))
        print(f"{index}. {candidate.get('name')} | fit={fit_score} | contact={contact}")


def stringify_field(value: Any) -> str:
    return stringify(unwrap_field(value))


def unwrap_field(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=True)


def to_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


if __name__ == "__main__":
    raise SystemExit(main())
