from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from automation.clients.lightfield_client import LightfieldClient
from automation.clients.parallel_monitor_client import ParallelMonitorClient
from automation.clients.parallel_task_client import ParallelTaskClient
from automation.config import Settings
from automation.db import IdentityStore
from automation.services.enrichment_service import EnrichmentService
from automation.services.lightfield_sync_service import LightfieldSyncService
from automation.services.scoring_service import ScoringService
from automation.utils import compact_json


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Lightfield Parallel Prospect Engine", version="0.1.0")

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhooks/parallel")
    async def handle_parallel_webhook(request: Request) -> dict[str, Any]:
        current_settings = settings or Settings.from_env()
        store = IdentityStore(current_settings.identity_db_path)

        raw_body = await request.body()
        webhook_id = request.headers.get("webhook-id") or hashlib.sha256(raw_body).hexdigest()

        if store.has_processed_event("parallel-webhook", webhook_id):
            return {"status": "duplicate", "webhook_id": webhook_id}

        _verify_parallel_signature(current_settings, request, raw_body)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

        event_type = payload.get("type")
        if event_type != "monitor.event.detected":
            store.mark_event_processed("parallel-webhook", webhook_id, payload)
            return {"status": "ignored", "type": event_type}

        monitor_data = payload.get("data") or {}
        monitor_id = monitor_data.get("monitor_id")
        event_group_id = (
            ((monitor_data.get("event") or {}).get("event_group_id"))
            or monitor_data.get("event_group_id")
        )
        metadata = monitor_data.get("metadata") or {}

        if not monitor_id:
            raise HTTPException(status_code=400, detail="Missing monitor_id in webhook payload.")

        company_name = metadata.get("company_name") or metadata.get("company") or metadata.get("account_name")
        website = metadata.get("website") or metadata.get("account_website")

        event_group: dict[str, Any] = {}
        if event_group_id:
            monitor_client = ParallelMonitorClient(current_settings)
            event_group = monitor_client.get_event_group(monitor_id=monitor_id, event_group_id=event_group_id)

        if not company_name:
            store.record_dead_letter(
                source="parallel-monitor",
                reference_key=event_group_id or webhook_id,
                payload=payload,
                error_message="Webhook did not include company_name metadata.",
            )
            store.mark_event_processed("parallel-webhook", webhook_id, payload)
            return {
                "status": "dead_letter",
                "reason": "missing company_name metadata",
                "event_group_id": event_group_id,
            }

        task_client = ParallelTaskClient(current_settings)
        enrichment_service = EnrichmentService(
            settings=current_settings,
            task_client=task_client,
            scoring_service=ScoringService(),
        )
        profile = enrichment_service.enrich_company(
            company_name=company_name,
            website=website,
            signal_context=compact_json(event_group) if event_group else event_group_id,
        )

        sync_service = LightfieldSyncService(
            settings=current_settings,
            client=LightfieldClient(current_settings),
            store=store,
        )
        sync_result = sync_service.sync_profile(profile, dry_run=current_settings.dry_run)

        store.mark_event_processed("parallel-webhook", webhook_id, payload)
        if event_group_id:
            store.mark_event_processed("parallel-monitor", event_group_id, payload)

        return {
            "status": "processed",
            "event_group_id": event_group_id,
            "sync": sync_result.model_dump(),
        }

    return app


def _verify_parallel_signature(settings: Settings, request: Request, raw_body: bytes) -> None:
    if not settings.parallel_webhook_secret:
        return

    webhook_id = request.headers.get("webhook-id")
    webhook_timestamp = request.headers.get("webhook-timestamp")
    webhook_signature = request.headers.get("webhook-signature")
    if not webhook_id or not webhook_timestamp or not webhook_signature:
        raise HTTPException(status_code=401, detail="Missing Parallel webhook signature headers.")

    signed_payload = b".".join(
        [
            webhook_id.encode("utf-8"),
            webhook_timestamp.encode("utf-8"),
            raw_body,
        ]
    )
    expected_signature = base64.b64encode(
        hmac.new(
            settings.parallel_webhook_secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    for part in webhook_signature.split(" "):
        version, _, signature = part.partition(",")
        if version == "v1" and hmac.compare_digest(signature, expected_signature):
            return

    raise HTTPException(status_code=401, detail="Invalid Parallel webhook signature.")


app = create_app()
