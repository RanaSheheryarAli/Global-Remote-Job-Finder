import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

SourceType = Literal["greenhouse", "lever", "ashby", "remoteok"]
ProviderRegion = Literal["global", "eu"]
DOMAIN_RE = re.compile(r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")


class SourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    source_type: SourceType = "greenhouse"
    board_token: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_-]+$")
    company_domain: str | None = Field(default=None, max_length=255)
    career_url: HttpUrl | None = None
    provider_region: ProviderRegion = "global"
    headquarters_country: str | None = Field(default=None, min_length=2, max_length=2)
    is_gcc: bool = False
    is_aggregator: bool = False
    requires_attribution: bool = False
    attribution_name: str | None = Field(default=None, max_length=100)
    attribution_url: HttpUrl | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not any(character.isalpha() for character in value) or "/" in value:
            raise ValueError("Company/source name must be human-readable")
        return value

    @field_validator("company_domain")
    @classmethod
    def validate_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not DOMAIN_RE.fullmatch(value):
            raise ValueError("Company domain must be a hostname without a URL scheme or path")
        return value

    @field_validator("headquarters_country")
    @classmethod
    def uppercase_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def validate_provider_rules(self) -> "SourceCreate":
        if self.source_type != "lever" and self.provider_region != "global":
            raise ValueError("Only Lever sources may select the EU provider region")
        if self.source_type == "remoteok":
            if self.board_token != "remoteok" or not self.is_aggregator:
                raise ValueError("Remote OK must use identifier 'remoteok' as an aggregator")
            if not self.requires_attribution:
                raise ValueError("Remote OK requires visible attribution and a followed link back")
            if self.attribution_name != "Remote OK" or self.attribution_url is None:
                raise ValueError("Remote OK attribution name and URL are required")
        elif self.is_aggregator:
            raise ValueError("Only the Remote OK source may be marked as an aggregator")
        return self


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: str
    board_token: str
    company_domain: str | None
    career_url: str | None
    provider_region: str
    headquarters_country: str | None
    is_gcc: bool
    is_aggregator: bool
    requires_attribution: bool
    attribution_name: str | None
    attribution_url: str | None
    enabled: bool
    health_status: str
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    circuit_open_until: datetime | None
    consecutive_failures: int
    last_job_count: int | None
    last_error_summary: str | None
    validated_at: datetime | None
    validation_sample_url: str | None
    created_at: datetime
    updated_at: datetime


class IngestionReportRead(BaseModel):
    source_id: UUID
    run_id: UUID
    received_count: int
    new_count: int
    changed_count: int
    unchanged_count: int
    deactivated_count: int


class SourceValidationRead(BaseModel):
    source_id: UUID
    source_type: str
    job_count: int
    sample_url: str
    health_status: str
    validated_at: datetime


class SourceHealthSummary(BaseModel):
    total: int
    enabled: int
    healthy: int
    degraded: int
    failing: int
    unknown: int
    circuits_open: int
    sources: list[SourceRead]


class SeedResultRead(BaseModel):
    created: int
    existing: int
    total_definitions: int
