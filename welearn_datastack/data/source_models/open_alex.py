from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class Meta(BaseModel):
    count: int
    db_response_time_ms: int
    page: int
    per_page: int
    groups_count: Any


class Ids(BaseModel):
    openalex: str
    doi: str
    mag: str
    pmid: str
    pmcid: str


class Author(BaseModel):
    id: str
    display_name: str
    orcid: Optional[str]


class Institution(BaseModel):
    id: str
    display_name: str
    ror: str
    country_code: Optional[str]
    type: str
    lineage: List[str]


class Affiliation(BaseModel):
    raw_affiliation_string: str
    institution_ids: List[str]


class Authorship(BaseModel):
    author_position: str
    author: Author
    institutions: List[Institution]
    countries: List[str]
    is_corresponding: bool
    raw_author_name: str
    raw_affiliation_strings: List[str]
    affiliations: List[Affiliation]


class OpenAccess(BaseModel):
    is_oa: bool
    oa_status: str
    oa_url: str
    any_repository_has_fulltext: bool


class Source(BaseModel):
    id: str
    display_name: str
    issn_l: str
    issn: List[str]
    is_oa: bool
    is_in_doaj: bool
    is_indexed_in_scopus: bool
    is_core: bool
    host_organization: Any
    host_organization_name: Any
    host_organization_lineage: List
    host_organization_lineage_names: List
    type: str


class BestOaLocation(BaseModel):
    is_oa: bool
    landing_page_url: str
    pdf_url: str
    source: Source
    license: str
    license_id: str
    version: str
    is_accepted: bool
    is_published: bool


class Subfield(BaseModel):
    id: str
    display_name: str


class Field(BaseModel):
    id: str
    display_name: str


class Domain(BaseModel):
    id: str
    display_name: str


class Topic(BaseModel):
    id: str
    display_name: str
    score: float
    subfield: Subfield
    field: Field
    domain: Domain


class Keyword(BaseModel):
    id: str
    display_name: str
    score: float


class Source1(BaseModel):
    id: str
    display_name: str
    issn_l: Optional[str]
    issn: Optional[List[str]]
    is_oa: bool
    is_in_doaj: bool
    is_indexed_in_scopus: bool
    is_core: bool
    host_organization: Optional[str]
    host_organization_name: Optional[str]
    host_organization_lineage: List[str]
    host_organization_lineage_names: List[str]
    type: str


class Location(BaseModel):
    is_oa: bool
    landing_page_url: str
    pdf_url: Optional[str]
    source: Source1
    license: Optional[str]
    license_id: Optional[str]
    version: Optional[str]
    is_accepted: bool
    is_published: bool


class OpenAlexResult(BaseModel):
    title: str
    ids: Ids
    language: str
    publication_date: str
    authorships: List[Authorship]
    open_access: OpenAccess
    best_oa_location: BestOaLocation
    abstract_inverted_index: dict[str, list[int]]
    type: str
    topics: List[Topic]
    keywords: List[Keyword]
    referenced_works: List[str]
    related_works: List[str]
    locations: Optional[List[Location]]


class OpenAlexModel(BaseModel):
    meta: Meta
    results: List[OpenAlexResult]
    group_by: List
