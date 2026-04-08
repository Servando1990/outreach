from __future__ import annotations

from pydantic import BaseModel, Field


class MonitorEventReference(BaseModel):
    event_group_id: str | None = None


class MonitorWebhookData(BaseModel):
    monitor_id: str
    event: MonitorEventReference | dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)


class MonitorWebhookPayload(BaseModel):
    type: str
    timestamp: str
    data: MonitorWebhookData
