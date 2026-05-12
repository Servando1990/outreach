from __future__ import annotations

from typing import Any

import httpx
from parallel import APIStatusError, Parallel

from automation.config import Settings


class ParallelMonitorClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.require_parallel()
        self.client = Parallel(
            api_key=self.settings.parallel_api_key,
            base_url=self.settings.parallel_base_url,
            timeout=self.settings.parallel_timeout_seconds,
        )

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self.client.get(
            path,
            cast_to=httpx.Response,
            options={"params": params or {}},
        )
        if not response.content:
            return None
        return response.json()

    def _post(self, path: str, *, body: dict[str, Any]) -> Any:
        response = self.client.post(path, cast_to=httpx.Response, body=body)
        if not response.content:
            return None
        return response.json()

    def create_monitor(
        self,
        *,
        query: str,
        webhook_url: str,
        cadence: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "query": query,
            "cadence": cadence or self.settings.monitor_cadence,
            "metadata": metadata or {},
            "webhook": {
                "url": webhook_url,
                "event_types": ["monitor.event.detected"],
            },
        }
        try:
            return self._post("/v1alpha/monitors", body=payload)
        except APIStatusError as exc:
            response_text = exc.response.text.lower() if exc.response else ""
            if exc.status_code == 422 and "frequency" in response_text:
                fallback_payload = dict(payload)
                fallback_payload["frequency"] = fallback_payload.pop("cadence")
                return self._post("/v1alpha/monitors", body=fallback_payload)
            raise

    def list_monitors(self, *, limit: int | None = None, cursor: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor:
            params["monitor_id"] = cursor
        return self._get("/v1alpha/monitors", params=params)

    def get_event_group(self, monitor_id: str, event_group_id: str) -> dict[str, Any]:
        return self._get(
            f"/v1alpha/monitors/{monitor_id}/event_groups/{event_group_id}",
        )
