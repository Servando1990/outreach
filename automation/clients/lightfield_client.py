from __future__ import annotations

from typing import Any

import httpx

from automation.config import Settings


class LightfieldClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._account_definitions: dict[str, Any] | None = None
        self._contact_definitions: dict[str, Any] | None = None

    def _headers(self, *, idempotency_key: str | None = None) -> dict[str, str]:
        self.settings.require_lightfield()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.lightfield_api_key or ''}",
            "Lightfield-Version": self.settings.lightfield_version,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        idempotency_key = kwargs.pop("idempotency_key", None)
        with httpx.Client(timeout=self.settings.parallel_timeout_seconds) as client:
            response = client.request(
                method,
                f"{self.settings.lightfield_base_url}{path}",
                headers=self._headers(idempotency_key=idempotency_key),
                **kwargs,
            )
            response.raise_for_status()
            if not response.content:
                return None
            return response.json()

    def get_account_definitions(self, *, force_refresh: bool = False) -> dict[str, Any]:
        if not self.settings.lightfield_api_key:
            return {"fieldDefinitions": {}, "relationshipDefinitions": {}}
        if self._account_definitions is None or force_refresh:
            self._account_definitions = self._request("GET", "/v1/accounts/definitions")
        return self._account_definitions

    def get_contact_definitions(self, *, force_refresh: bool = False) -> dict[str, Any]:
        if not self.settings.lightfield_api_key:
            return {"fieldDefinitions": {}, "relationshipDefinitions": {}}
        if self._contact_definitions is None or force_refresh:
            self._contact_definitions = self._request("GET", "/v1/contacts/definitions")
        return self._contact_definitions

    def account_field_exists(self, key: str) -> bool:
        if not self.settings.lightfield_api_key:
            return False
        definitions = self.get_account_definitions()
        field = (definitions.get("fieldDefinitions") or {}).get(key)
        return bool(field and not field.get("readOnly"))

    def contact_field_exists(self, key: str) -> bool:
        if not self.settings.lightfield_api_key:
            return False
        definitions = self.get_contact_definitions()
        field = (definitions.get("fieldDefinitions") or {}).get(key)
        return bool(field and not field.get("readOnly"))

    def list_accounts(
        self,
        *,
        filters: dict[str, tuple[str, str | None]] | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {"limit": min(limit, 25), "offset": offset}
        for field_key, (value, operator) in (filters or {}).items():
            if operator is None:
                params[field_key] = value
            else:
                params[f"{field_key}[{operator}]"] = value
        return self._request("GET", "/v1/accounts", params=params)

    def list_contacts(
        self,
        *,
        filters: dict[str, tuple[str, str | None]] | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {"limit": min(limit, 25), "offset": offset}
        for field_key, (value, operator) in (filters or {}).items():
            if operator is None:
                params[field_key] = value
            else:
                params[f"{field_key}[{operator}]"] = value
        return self._request("GET", "/v1/contacts", params=params)

    def find_account_by_field(
        self,
        *,
        field_key: str,
        value: str,
        operator: str | None = None,
    ) -> dict[str, Any] | None:
        response = self.list_accounts(filters={field_key: (value, operator)}, limit=1)
        records = response.get("data") or []
        return records[0] if records else None

    def find_contact_by_field(
        self,
        *,
        field_key: str,
        value: str,
        operator: str | None = None,
    ) -> dict[str, Any] | None:
        response = self.list_contacts(filters={field_key: (value, operator)}, limit=1)
        records = response.get("data") or []
        return records[0] if records else None

    def create_account(
        self,
        *,
        fields: dict[str, Any],
        relationships: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"fields": fields}
        if relationships:
            payload["relationships"] = relationships
        return self._request(
            "POST",
            "/v1/accounts",
            json=payload,
            idempotency_key=idempotency_key,
        )

    def update_account(
        self,
        *,
        account_id: str,
        fields: dict[str, Any] | None = None,
        relationships: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if fields:
            payload["fields"] = fields
        if relationships:
            payload["relationships"] = relationships
        return self._request(
            "POST",
            f"/v1/accounts/{account_id}",
            json=payload,
            idempotency_key=idempotency_key,
        )

    def create_contact(
        self,
        *,
        fields: dict[str, Any],
        relationships: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"fields": fields}
        if relationships:
            payload["relationships"] = relationships
        return self._request(
            "POST",
            "/v1/contacts",
            json=payload,
            idempotency_key=idempotency_key,
        )

    def update_contact(
        self,
        *,
        contact_id: str,
        fields: dict[str, Any] | None = None,
        relationships: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if fields:
            payload["fields"] = fields
        if relationships:
            payload["relationships"] = relationships
        return self._request(
            "POST",
            f"/v1/contacts/{contact_id}",
            json=payload,
            idempotency_key=idempotency_key,
        )
