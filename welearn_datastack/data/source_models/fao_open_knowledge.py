from typing import Any

from pydantic import BaseModel, Field


class Bundles(BaseModel):
    href: str


class MappedCollections(BaseModel):
    href: str


class OwningCollection(BaseModel):
    href: str


class Relationships(BaseModel):
    href: str


class Version(BaseModel):
    href: str


class TemplateItemOf(BaseModel):
    href: str


class Thumbnail(BaseModel):
    href: str


class Relateditemlistconfigs(BaseModel):
    href: str


class Self(BaseModel):
    href: str


class _Links(BaseModel):
    bundles: Bundles
    mappedCollections: MappedCollections
    owningCollection: OwningCollection
    relationships: Relationships
    version: Version
    templateItemOf: TemplateItemOf
    thumbnail: Thumbnail
    relateditemlistconfigs: Relateditemlistconfigs
    self: Self


class Item(BaseModel):
    id: str
    uuid: str
    name: str
    handle: str
    metadata: dict[str, Any]
    inArchive: bool
    discoverable: bool
    withdrawn: bool
    lastModified: str
    entityType: Any
    type: str
    _links: _Links


class Embedded(BaseModel):
    items: list[Item]


class Next(BaseModel):
    href: str


class Last(BaseModel):
    href: str


class Self1(BaseModel):
    href: str


class Links1(BaseModel):
    next: Next
    last: Last
    self: Self1


class Page(BaseModel):
    number: int
    size: int
    totalPages: int
    totalElements: int


class FaoOKModel(BaseModel):
    embedded: Embedded = Field(..., alias="_embedded")
    links: Links1 = Field(..., alias="_links")
    page: Page
