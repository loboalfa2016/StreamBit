from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


ProviderName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
ProviderCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
ResourceIdentifier = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
AuthorizationReference = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)
]


class ProviderCreate(BaseModel):
    name: ProviderName
    code: ProviderCode
    base_url: Annotated[str, StringConstraints(max_length=500)] | None = None
    is_active: bool = True


class ProviderResponse(BaseModel):
    id: int
    name: str
    code: str
    base_url: str | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceCreate(BaseModel):
    movie_id: int
    provider_id: int
    resource_identifier: ResourceIdentifier
    territories: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    subtitles: list[str] = Field(default_factory=list)
    authorization_reference: AuthorizationReference
    authorization_terms: str | None = None
    is_active: bool = True
    is_verified: bool = False


class SourceUpdate(BaseModel):
    provider_id: int | None = None
    resource_identifier: ResourceIdentifier | None = None
    territories: list[str] | None = None
    languages: list[str] | None = None
    subtitles: list[str] | None = None
    authorization_reference: AuthorizationReference | None = None
    authorization_terms: str | None = None
    is_active: bool | None = None
    is_verified: bool | None = None

    @field_validator(
        "provider_id",
        "resource_identifier",
        "territories",
        "languages",
        "subtitles",
        "authorization_reference",
        "is_active",
        "is_verified",
    )
    @classmethod
    def reject_null_for_required_fields(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("Este campo no puede ser nulo.")
        return value


class SourceResponse(BaseModel):
    id: int
    movie_id: int
    provider_id: int
    resource_identifier: str
    territories: list[str]
    languages: list[str]
    subtitles: list[str]
    authorization_reference: str
    authorization_terms: str | None = None
    is_active: bool
    is_verified: bool
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
