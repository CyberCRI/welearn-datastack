from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Creator(BaseModel):
    name: str
    affiliation: Any


class RelatedIdentifier(BaseModel):
    identifier: str
    relation: str
    resource_type: str
    scheme: str


class ResourceType(BaseModel):
    title: str
    type: str
    subtype: str


class License(BaseModel):
    id: str


class Community(BaseModel):
    id: str


class Parent(BaseModel):
    pid_type: str
    pid_value: str


class VersionItem(BaseModel):
    index: int
    is_last: bool
    parent: Parent


class Relations(BaseModel):
    version: List[VersionItem]


class Metadata(BaseModel):
    title: str
    doi: str
    publication_date: str
    description: str
    access_right: str
    creators: List[Creator]
    related_identifiers: List[RelatedIdentifier] = Field(default_factory=list)
    resource_type: ResourceType
    license: License
    communities: List[Community]
    relations: Relations


class Thumbnails(BaseModel):
    field_10: str = Field(..., alias="10")
    field_50: str = Field(..., alias="50")
    field_100: str = Field(..., alias="100")
    field_250: str = Field(..., alias="250")
    field_750: str = Field(..., alias="750")
    field_1200: str = Field(..., alias="1200")


class Links(BaseModel):
    self: str
    self_html: str
    preview_html: str
    doi: str
    self_doi: str
    self_doi_html: str
    reserve_doi: str
    parent: str
    parent_html: str
    parent_doi: str
    parent_doi_html: str
    self_iiif_manifest: str
    self_iiif_sequence: str
    files: str
    media_files: str
    thumbnails: Thumbnails
    archive: str
    archive_media: str
    latest: str
    latest_html: str
    versions: str
    draft: str
    access_links: str
    access_grants: str
    access_users: str
    access_request: str
    access: str
    communities: str
    communities_suggestions: str = Field(..., alias="communities-suggestions")
    request_deletion: str
    file_modification: str
    quota_increase: str
    requests: str


class Links1(BaseModel):
    self: str


class File(BaseModel):
    id: str
    key: str
    size: int
    checksum: str
    links: Links1


class Owner(BaseModel):
    id: str


class Stats(BaseModel):
    downloads: int
    unique_downloads: int
    views: int
    unique_views: int
    version_downloads: int
    version_unique_downloads: int
    version_unique_views: int
    version_views: int


class ZenodoRecord(BaseModel):
    created: str
    modified: str
    id: int
    conceptrecid: str
    doi: str
    conceptdoi: str
    doi_url: str
    metadata: Metadata
    title: str
    links: Links
    updated: str
    recid: str
    revision: int
    files: List[File]
    swh: Dict[str, Any]
    owners: List[Owner]
    status: str
    stats: Stats
    state: str
    submitted: bool
