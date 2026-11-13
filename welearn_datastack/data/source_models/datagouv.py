from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class RootDataGouvModel(BaseModel):
    data: List[Dataset]
    total: int
    page_size: int = Field(gt=0)


class DataGouvOrganization(BaseModel):
    name: str | None = None


class Dataset(BaseModel):
    created_at: str
    description: str
    description_short: str | None = None
    doi: str | None = None
    frequency: str = "unknown"
    id: str | None = None
    last_modified: str
    license: str = "notspecified"
    organization: DataGouvOrganization | None = None
    page: str | None = None
    quality: Quality | None = None
    slug: str | None = None
    tags: list[str] = Field(default_factory=list)
    title: str


class Quality(BaseModel):
    all_resources_available: bool
    dataset_description_quality: bool
    has_open_format: bool
    has_resources: bool
    license: bool
    resources_documentation: bool
    score: int
    spatial: bool
    temporal_coverage: bool
    update_frequency: bool
    update_fulfilled_in_time: bool
