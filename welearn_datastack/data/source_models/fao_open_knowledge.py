from typing import Any

from pydantic import BaseModel, Field


class Link(BaseModel):
    href: str


class _Links(BaseModel):
    bundles: Link
    mappedCollections: Link
    owningCollection: Link
    relationships: Link
    version: Link
    templateItemOf: Link
    thumbnail: Link
    relateditemlistconfigs: Link
    self: Link


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


class BundleLinksModel(BaseModel):
    item: Link
    bitstreams: Link
    primaryBitstream: Link
    self: Link


class Bundle(BaseModel):
    uuid: str
    name: str
    handle: Any
    metadata: dict
    type: str
    links: BundleLinksModel = Field(..., alias="_links")


class MetadataEntry(BaseModel):
    value: str
    language: str
    authority: str | None
    confidence: int | None
    place: int


#
# class MetadataEntries(BaseModel):
#     metadata: list[MetadataEntry]
