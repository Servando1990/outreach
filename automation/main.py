from __future__ import annotations

import argparse
import json
from typing import Any

from automation.clients.lightfield_client import LightfieldClient
from automation.clients.parallel_monitor_client import ParallelMonitorClient
from automation.clients.parallel_task_client import ParallelTaskClient
from automation.config import Settings
from automation.db import IdentityStore
from automation.services.enrichment_service import EnrichmentService
from automation.services.lightfield_sync_service import LightfieldSyncService
from automation.services.scoring_service import ScoringService


def build_runtime(settings: Settings | None = None) -> dict[str, Any]:
    current_settings = settings or Settings.from_env()
    task_client = ParallelTaskClient(current_settings)
    lightfield_client = LightfieldClient(current_settings)
    monitor_client = ParallelMonitorClient(current_settings)
    store = IdentityStore(current_settings.identity_db_path)
    enrichment_service = EnrichmentService(
        settings=current_settings,
        task_client=task_client,
        scoring_service=ScoringService(),
    )
    sync_service = LightfieldSyncService(
        settings=current_settings,
        client=lightfield_client,
        store=store,
    )
    return {
        "settings": current_settings,
        "task_client": task_client,
        "lightfield_client": lightfield_client,
        "monitor_client": monitor_client,
        "store": store,
        "enrichment_service": enrichment_service,
        "sync_service": sync_service,
    }


def run_discover(*, query: str, limit: int | None = None, dry_run: bool | None = None) -> list[dict[str, Any]]:
    runtime = build_runtime()
    settings: Settings = runtime["settings"]
    settings.require_parallel()

    effective_dry_run = settings.effective_dry_run(dry_run)
    if not effective_dry_run:
        settings.require_lightfield()

    enrichment_service: EnrichmentService = runtime["enrichment_service"]
    sync_service: LightfieldSyncService = runtime["sync_service"]

    profiles = enrichment_service.discover(
        query=query,
        limit=limit or settings.discover_limit_default,
    )
    return [
        {
            "profile": profile.model_dump(),
            "sync": sync_service.sync_profile(profile, dry_run=effective_dry_run).model_dump(),
        }
        for profile in profiles
    ]


def run_backfill(
    *,
    csv_path: str | None = None,
    limit: int | None = None,
    dry_run: bool | None = None,
) -> list[dict[str, Any]]:
    runtime = build_runtime()
    settings: Settings = runtime["settings"]
    settings.require_parallel()

    effective_dry_run = settings.effective_dry_run(dry_run)
    if not effective_dry_run:
        settings.require_lightfield()

    enrichment_service: EnrichmentService = runtime["enrichment_service"]
    sync_service: LightfieldSyncService = runtime["sync_service"]

    profiles = enrichment_service.backfill_from_csv(
        csv_path=csv_path or settings.seed_csv,
        limit=limit,
    )
    return [
        {
            "profile": profile.model_dump(),
            "sync": sync_service.sync_profile(profile, dry_run=effective_dry_run).model_dump(),
        }
        for profile in profiles
    ]


def run_monitor_create(
    *,
    webhook_url: str,
    query: str | None = None,
    company_name: str,
    website: str | None = None,
    cadence: str | None = None,
) -> dict[str, Any]:
    runtime = build_runtime()
    settings: Settings = runtime["settings"]
    settings.require_parallel()

    monitor_query = query or (
        f"Recent fund activity, new mandates, team expansion, GTM/operator hiring, "
        f"or market expansion for {company_name} {f'({website})' if website else ''}"
    )

    monitor_client: ParallelMonitorClient = runtime["monitor_client"]
    return monitor_client.create_monitor(
        query=monitor_query,
        webhook_url=webhook_url,
        cadence=cadence or settings.monitor_cadence,
        metadata={
            "company_name": company_name,
            "website": website,
            "prompt_version": settings.prompt_version,
        },
    )


def run_monitor_list(*, limit: int | None = None) -> list[dict[str, Any]]:
    runtime = build_runtime()
    settings: Settings = runtime["settings"]
    settings.require_parallel()
    monitor_client: ParallelMonitorClient = runtime["monitor_client"]
    return monitor_client.list_monitors(limit=limit)


def serve_webhooks(*, host: str, port: int) -> int:
    import uvicorn

    uvicorn.run("automation.api.webhooks:app", host=host, port=port, reload=False)
    return 0


def _resolve_dry_run(settings: Settings, args: argparse.Namespace) -> bool | None:
    if getattr(args, "dry_run", False):
        return True
    if getattr(args, "live", False):
        return False
    return settings.dry_run


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prospect-engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover", help="Search for new prospects with Parallel, then enrich and sync.")
    discover.add_argument("--query", required=True, help="Natural-language prospect search query.")
    discover.add_argument("--limit", type=int, default=None, help="Maximum number of prospects to process.")
    discover_group = discover.add_mutually_exclusive_group()
    discover_group.add_argument("--dry-run", action="store_true", help="Preview without writing to Lightfield.")
    discover_group.add_argument("--live", action="store_true", help="Write to Lightfield.")

    backfill = subparsers.add_parser("backfill", help="Enrich a seed CSV and sync the results.")
    backfill.add_argument("--csv", default=None, help="CSV path. Defaults to SEED_CSV.")
    backfill.add_argument("--limit", type=int, default=None, help="Maximum number of rows to process.")
    backfill_group = backfill.add_mutually_exclusive_group()
    backfill_group.add_argument("--dry-run", action="store_true", help="Preview without writing to Lightfield.")
    backfill_group.add_argument("--live", action="store_true", help="Write to Lightfield.")

    monitor_create = subparsers.add_parser("monitor-create", help="Create a Parallel monitor for an account or custom query.")
    monitor_create.add_argument("--webhook-url", required=True, help="Webhook endpoint that receives Monitor events.")
    monitor_create.add_argument("--query", default=None, help="Custom Monitor query.")
    monitor_create.add_argument("--company-name", required=True, help="Account name for account-specific monitoring.")
    monitor_create.add_argument("--website", default=None, help="Company website to include in metadata.")
    monitor_create.add_argument("--cadence", default=None, help="Monitor cadence. Defaults to MONITOR_CADENCE.")

    monitor_list = subparsers.add_parser("monitor-list", help="List existing Parallel monitors.")
    monitor_list.add_argument("--limit", type=int, default=None, help="Optional page size.")

    serve = subparsers.add_parser("serve-webhooks", help="Run the FastAPI webhook server locally.")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    dry_run = _resolve_dry_run(settings, args)

    if args.command == "discover":
        _print_json(run_discover(query=args.query, limit=args.limit, dry_run=dry_run))
        return 0
    if args.command == "backfill":
        _print_json(run_backfill(csv_path=args.csv, limit=args.limit, dry_run=dry_run))
        return 0
    if args.command == "monitor-create":
        _print_json(
            run_monitor_create(
                webhook_url=args.webhook_url,
                query=args.query,
                company_name=args.company_name,
                website=args.website,
                cadence=args.cadence,
            )
        )
        return 0
    if args.command == "monitor-list":
        _print_json(run_monitor_list(limit=args.limit))
        return 0
    if args.command == "serve-webhooks":
        return serve_webhooks(host=args.host, port=args.port)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
