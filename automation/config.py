from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ICP_DESCRIPTION = (
    "Placement agents, PE firms, capital advisory boutiques, and small VC firms "
    "that likely need outbound prospecting, CRM enrichment, or lead generation "
    "automation."
)


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


@dataclass(slots=True)
class Settings:
    lightfield_api_key: str | None
    parallel_api_key: str | None
    parallel_webhook_secret: str | None

    lightfield_base_url: str
    lightfield_version: str
    parallel_base_url: str
    parallel_processor: str
    parallel_timeout_seconds: int
    parallel_result_timeout_seconds: int
    parallel_poll_interval_seconds: int

    dry_run: bool
    prompt_version: str
    identity_db_path: str
    seed_csv: str
    discover_limit_default: int
    monitor_cadence: str
    icp_description: str

    lightfield_account_external_key_field: str
    lightfield_account_fit_score_field: str
    lightfield_account_fit_bucket_field: str
    lightfield_account_trigger_summary_field: str
    lightfield_account_prompt_version_field: str
    lightfield_account_source_urls_field: str
    lightfield_account_last_signal_at_field: str

    lightfield_contact_linkedin_field: str
    lightfield_contact_role_title_field: str
    lightfield_contact_role_confidence_field: str
    lightfield_contact_source_urls_field: str

    @classmethod
    def from_env(cls, env_path: str | Path = ".env") -> "Settings":
        load_dotenv(env_path)
        return cls(
            lightfield_api_key=os.getenv("LIGHTFIELD_API_KEY"),
            parallel_api_key=os.getenv("PARALLEL_API_KEY"),
            parallel_webhook_secret=os.getenv("PARALLEL_WEBHOOK_SECRET"),
            lightfield_base_url=os.getenv("LIGHTFIELD_BASE_URL", "https://api.lightfield.app").rstrip("/"),
            lightfield_version=os.getenv("LIGHTFIELD_VERSION", "2026-03-01"),
            parallel_base_url=os.getenv("PARALLEL_BASE_URL", "https://api.parallel.ai").rstrip("/"),
            parallel_processor=os.getenv("PARALLEL_PROCESSOR", "core"),
            parallel_timeout_seconds=_parse_int(os.getenv("PARALLEL_TIMEOUT_SECONDS"), 900),
            parallel_result_timeout_seconds=_parse_int(os.getenv("PARALLEL_RESULT_TIMEOUT_SECONDS"), 600),
            parallel_poll_interval_seconds=_parse_int(os.getenv("PARALLEL_POLL_INTERVAL_SECONDS"), 5),
            dry_run=_parse_bool(os.getenv("DRY_RUN"), True),
            prompt_version=os.getenv("PROMPT_VERSION", "prospect_profile_v1"),
            identity_db_path=os.getenv("IDENTITY_DB_PATH", "automation_state.db"),
            seed_csv=os.getenv("SEED_CSV", "master_merged_agents_contacts_crm_import.csv"),
            discover_limit_default=_parse_int(os.getenv("DISCOVER_LIMIT_DEFAULT"), 10),
            monitor_cadence=os.getenv("MONITOR_CADENCE", "daily"),
            icp_description=os.getenv("ICP_DESCRIPTION", DEFAULT_ICP_DESCRIPTION),
            lightfield_account_external_key_field=os.getenv(
                "LIGHTFIELD_ACCOUNT_EXTERNAL_KEY_FIELD",
                "external_company_key",
            ),
            lightfield_account_fit_score_field=os.getenv(
                "LIGHTFIELD_ACCOUNT_FIT_SCORE_FIELD",
                "outbound_fit_score",
            ),
            lightfield_account_fit_bucket_field=os.getenv(
                "LIGHTFIELD_ACCOUNT_FIT_BUCKET_FIELD",
                "outbound_fit_bucket",
            ),
            lightfield_account_trigger_summary_field=os.getenv(
                "LIGHTFIELD_ACCOUNT_TRIGGER_SUMMARY_FIELD",
                "trigger_summary",
            ),
            lightfield_account_prompt_version_field=os.getenv(
                "LIGHTFIELD_ACCOUNT_PROMPT_VERSION_FIELD",
                "prompt_version",
            ),
            lightfield_account_source_urls_field=os.getenv(
                "LIGHTFIELD_ACCOUNT_SOURCE_URLS_FIELD",
                "source_urls",
            ),
            lightfield_account_last_signal_at_field=os.getenv(
                "LIGHTFIELD_ACCOUNT_LAST_SIGNAL_AT_FIELD",
                "last_signal_at",
            ),
            lightfield_contact_linkedin_field=os.getenv(
                "LIGHTFIELD_CONTACT_LINKEDIN_FIELD",
                "linkedin_url",
            ),
            lightfield_contact_role_title_field=os.getenv(
                "LIGHTFIELD_CONTACT_ROLE_TITLE_FIELD",
                "role_title",
            ),
            lightfield_contact_role_confidence_field=os.getenv(
                "LIGHTFIELD_CONTACT_ROLE_CONFIDENCE_FIELD",
                "role_confidence",
            ),
            lightfield_contact_source_urls_field=os.getenv(
                "LIGHTFIELD_CONTACT_SOURCE_URLS_FIELD",
                "source_urls",
            ),
        )

    def effective_dry_run(self, override: bool | None = None) -> bool:
        if override is None:
            return self.dry_run
        return override

    def require_parallel(self) -> None:
        if not self.parallel_api_key:
            raise RuntimeError("PARALLEL_API_KEY is required for this command.")

    def require_lightfield(self) -> None:
        if not self.lightfield_api_key:
            raise RuntimeError("LIGHTFIELD_API_KEY is required for this command.")
