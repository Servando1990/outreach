from __future__ import annotations

from pydantic import BaseModel, Field


class ContactSyncResult(BaseModel):
    full_name: str | None = None
    email: str | None = None
    contact_id: str | None = None
    action: str


class SyncResult(BaseModel):
    mode: str
    external_company_key: str
    account_id: str | None = None
    account_action: str
    contacts: list[ContactSyncResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
