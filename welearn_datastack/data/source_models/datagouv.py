from __future__ import annotations

from typing import List

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
    doi: str | None = None
    frequency: str | None = None
    id: str
    last_modified: str
    license: str | None = None
    organization: DataGouvOrganization | None = None
    page: str | None = None
    slug: str | None = None
    tags: list[str] = Field(default_factory=list)
    title: str
