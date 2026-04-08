from __future__ import annotations

from typing import Any

import httpx

from automation.config import Settings


class ParallelMonitorClient:
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
            return self._request("POST", "/v1alpha/monitors", json=payload)
        except httpx.HTTPStatusError as exc:
            response_text = exc.response.text.lower()
            if exc.response.status_code == 422 and "frequency" in response_text:
                fallback_payload = dict(payload)
                fallback_payload["frequency"] = fallback_payload.pop("cadence")
                return self._request("POST", "/v1alpha/monitors", json=fallback_payload)
            raise

    def list_monitors(self, *, limit: int | None = None, cursor: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor:
            params["monitor_id"] = cursor
        return self._request("GET", "/v1alpha/monitors", params=params)

    def get_event_group(self, monitor_id: str, event_group_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/v1alpha/monitors/{monitor_id}/event_groups/{event_group_id}",
        )
