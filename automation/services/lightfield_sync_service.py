from __future__ import annotations

from automation.clients.lightfield_client import LightfieldClient
from automation.config import Settings
from automation.db import IdentityStore
from automation.models.crm_sync import ContactSyncResult, SyncResult
from automation.models.prospect import DecisionMaker, ProspectProfile
from automation.utils import (
    company_external_key,
    extract_domain,
    normalize_company_name,
    normalize_email,
    split_full_name,
    stable_hash,
    unique_strings,
)


class LightfieldSyncService:
    def __init__(
        self,
        *,
        settings: Settings,
        client: LightfieldClient,
        store: IdentityStore,
    ) -> None:
        self.settings = settings
        self.client = client
        self.store = store

    def sync_profile(self, profile: ProspectProfile, *, dry_run: bool | None = None) -> SyncResult:
        dry_run_enabled = self.settings.effective_dry_run(dry_run)
        external_key = company_external_key(profile.company_name, profile.website)
        normalized_domain = extract_domain(profile.website)
        normalized_company_name = normalize_company_name(profile.company_name)

        account_record = self._find_account(profile, external_key)
        account_fields = self._build_account_fields(profile, external_key)
        warnings: list[str] = []

        if dry_run_enabled:
            account_id = (account_record or {}).get("id") or f"dryrun-account-{stable_hash(external_key, length=10)}"
            account_action = "matched" if account_record else "create"
        else:
            if account_record:
                response = self.client.update_account(
                    account_id=account_record["id"],
                    fields=account_fields,
                    idempotency_key=stable_hash("account-update", external_key),
                )
                account_id = response["id"]
                account_action = "updated"
            else:
                response = self.client.create_account(
                    fields=account_fields,
                    idempotency_key=stable_hash("account-create", external_key),
                )
                account_id = response["id"]
                account_action = "created"
            self.store.upsert_account_mapping(
                external_company_key=external_key,
                normalized_company_name=normalized_company_name,
                normalized_domain=normalized_domain,
                lightfield_account_id=account_id,
            )

        contacts: list[ContactSyncResult] = []
        for decision_maker in profile.decision_makers:
            if not (decision_maker.full_name or decision_maker.email or decision_maker.linkedin_url):
                warnings.append("Skipped a decision-maker with no identifying fields.")
                continue
            contacts.append(
                self._sync_contact(
                    decision_maker=decision_maker,
                    account_id=account_id,
                    external_company_key=external_key,
                    dry_run=dry_run_enabled,
                )
            )

        result = SyncResult(
            mode="dry_run" if dry_run_enabled else "live",
            external_company_key=external_key,
            account_id=account_id,
            account_action=account_action,
            contacts=contacts,
            warnings=warnings,
        )
        self.store.record_sync_run(result.mode, external_key, "success", result.account_action)
        return result

    def sync_account_list(
        self,
        *,
        name: str,
        account_ids: list[str],
        dry_run: bool | None = None,
    ) -> dict[str, object]:
        dry_run_enabled = self.settings.effective_dry_run(dry_run)
        unique_account_ids = unique_strings(account_ids)
        if dry_run_enabled:
            return {
                "mode": "dry_run",
                "list_id": f"dryrun-list-{stable_hash(name, length=10)}",
                "list_name": name,
                "list_action": "create_or_update",
                "account_ids": unique_account_ids,
            }

        existing_list = self._find_account_list_by_name(name)
        if existing_list:
            response = self.client.update_list(
                list_id=existing_list["id"],
                relationships={"$accounts": {"add": unique_account_ids}},
                idempotency_key=stable_hash("list-update", name, *unique_account_ids),
            )
            action = "updated"
        else:
            response = self.client.create_list(
                name=name,
                object_type="account",
                relationships={"$accounts": unique_account_ids},
                idempotency_key=stable_hash("list-create", name),
            )
            action = "created"

        return {
            "mode": "live",
            "list_id": response.get("id"),
            "list_name": name,
            "list_action": action,
            "http_link": response.get("httpLink"),
            "account_ids": unique_account_ids,
        }

    def _find_account(self, profile: ProspectProfile, external_key: str) -> dict[str, str] | None:
        local_match = self.store.get_account_by_external_key(external_key)
        if local_match:
            return {"id": local_match["lightfield_account_id"]}

        if not self.settings.lightfield_api_key:
            return None

        if self.client.account_field_exists(self.settings.lightfield_account_external_key_field):
            remote_match = self.client.find_account_by_field(
                field_key=self.settings.lightfield_account_external_key_field,
                value=external_key,
            )
            if remote_match:
                return remote_match

        domain = extract_domain(profile.website)
        if domain:
            remote_match = self.client.find_account_by_field(
                field_key="$website",
                value=domain,
                operator="contains",
            )
            if remote_match:
                return remote_match

        return self.client.find_account_by_field(field_key="$name", value=profile.company_name)

    def _find_account_list_by_name(self, name: str) -> dict[str, str] | None:
        offset = 0
        while True:
            response = self.client.list_lists(limit=25, offset=offset)
            records = response.get("data") or []
            for record in records:
                fields = record.get("fields") or {}
                list_name = self._field_value(fields.get("$name"))
                object_type = self._field_value(fields.get("$objectType"))
                if list_name == name and object_type == "account":
                    return record
            if len(records) < 25:
                return None
            offset += 25

    def _field_value(self, field: object) -> object:
        if isinstance(field, dict) and "value" in field:
            return field.get("value")
        return field

    def _sync_contact(
        self,
        *,
        decision_maker: DecisionMaker,
        account_id: str,
        external_company_key: str,
        dry_run: bool,
    ) -> ContactSyncResult:
        email = normalize_email(decision_maker.email)
        linkedin_url = decision_maker.linkedin_url
        full_name = decision_maker.full_name
        identity_key = email or linkedin_url or f"{external_company_key}:{normalize_company_name(full_name or '')}"

        local_match = self.store.get_contact_by_identity(
            email=email,
            linkedin_url=linkedin_url,
            full_name=full_name,
            external_company_key=external_company_key,
        )

        remote_match = None
        if not local_match and not dry_run and email:
            remote_match = self.client.find_contact_by_field(
                field_key="$email",
                value=email,
                operator="contains",
            )
        if not local_match and not remote_match and not dry_run and linkedin_url and self.client.contact_field_exists(
            self.settings.lightfield_contact_linkedin_field
        ):
            remote_match = self.client.find_contact_by_field(
                field_key=self.settings.lightfield_contact_linkedin_field,
                value=linkedin_url,
                operator="contains",
            )

        existing_contact = {"id": local_match["lightfield_contact_id"]} if local_match else remote_match
        fields = self._build_contact_fields(decision_maker)
        relationships = {"$account": account_id}

        if dry_run:
            contact_id = (existing_contact or {}).get("id") or f"dryrun-contact-{stable_hash(identity_key, length=10)}"
            action = "matched" if existing_contact else "create"
        else:
            if existing_contact:
                response = self.client.update_contact(
                    contact_id=existing_contact["id"],
                    fields=fields,
                    relationships={"$account": {"add": account_id}},
                    idempotency_key=stable_hash("contact-update", identity_key),
                )
                contact_id = response["id"]
                action = "updated"
            else:
                response = self.client.create_contact(
                    fields=fields,
                    relationships=relationships,
                    idempotency_key=stable_hash("contact-create", identity_key),
                )
                contact_id = response["id"]
                action = "created"

            self.store.upsert_contact_mapping(
                identity_key=identity_key,
                external_company_key=external_company_key,
                full_name=full_name,
                email=email,
                linkedin_url=linkedin_url,
                lightfield_contact_id=contact_id,
            )

        return ContactSyncResult(
            full_name=full_name,
            email=email,
            contact_id=contact_id,
            action=action,
        )

    def _build_account_fields(self, profile: ProspectProfile, external_key: str) -> dict[str, object]:
        fields: dict[str, object] = {"$name": profile.company_name}

        if profile.website:
            fields["$website"] = unique_strings([profile.website])
        self._assign_account_custom_field(
            fields,
            self.settings.lightfield_account_external_key_field,
            external_key,
        )
        self._assign_account_custom_field(
            fields,
            self.settings.lightfield_account_fit_score_field,
            profile.outbound_fit_score,
        )
        self._assign_account_custom_field(
            fields,
            self.settings.lightfield_account_fit_bucket_field,
            profile.outbound_fit_bucket,
        )
        self._assign_account_custom_field(
            fields,
            self.settings.lightfield_account_trigger_summary_field,
            profile.recent_trigger_summary or profile.outbound_need_summary,
        )
        self._assign_account_custom_field(
            fields,
            self.settings.lightfield_account_prompt_version_field,
            profile.prompt_version,
        )
        self._assign_account_custom_field(
            fields,
            self.settings.lightfield_account_source_urls_field,
            "\n".join(unique_strings(profile.source_urls)),
        )
        self._assign_account_custom_field(
            fields,
            self.settings.lightfield_account_last_signal_at_field,
            profile.recent_trigger_date,
        )

        return fields

    def _build_contact_fields(self, decision_maker: DecisionMaker) -> dict[str, object]:
        first_name, last_name = split_full_name(decision_maker.full_name)
        fields: dict[str, object] = {}
        if first_name or last_name:
            fields["$name"] = {"firstName": first_name, "lastName": last_name}
        if decision_maker.email:
            fields["$email"] = unique_strings([decision_maker.email])
        if decision_maker.profile_photo_url:
            fields["$profilePhotoUrl"] = decision_maker.profile_photo_url

        self._assign_contact_custom_field(
            fields,
            self.settings.lightfield_contact_linkedin_field,
            decision_maker.linkedin_url,
        )
        self._assign_contact_custom_field(
            fields,
            self.settings.lightfield_contact_role_title_field,
            decision_maker.title,
        )
        self._assign_contact_custom_field(
            fields,
            self.settings.lightfield_contact_role_confidence_field,
            decision_maker.confidence,
        )
        self._assign_contact_custom_field(
            fields,
            self.settings.lightfield_contact_source_urls_field,
            "\n".join(unique_strings(decision_maker.source_urls)),
        )
        return fields

    def _assign_account_custom_field(self, fields: dict[str, object], field_key: str, value: object) -> None:
        if value is None:
            return
        if self.client.account_field_exists(field_key):
            fields[field_key] = value

    def _assign_contact_custom_field(self, fields: dict[str, object], field_key: str, value: object) -> None:
        if value is None:
            return
        if self.client.contact_field_exists(field_key):
            fields[field_key] = value
