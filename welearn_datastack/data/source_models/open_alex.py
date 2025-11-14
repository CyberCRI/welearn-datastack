from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class Meta(BaseModel):
    count: Optional[int] = None
    db_response_time_ms: Optional[int] = None
    page: Optional[int] = None
    per_page: Optional[int] = None
    groups_count: Optional[Any] = None


class Ids(BaseModel):
    openalex: Optional[str] = None
    doi: Optional[str] = None
    mag: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None


class Author(BaseModel):
    id: Optional[str] = None
    display_name: Optional[str] = None
    orcid: Optional[str] = None


class Institution(BaseModel):
    id: Optional[str] = None
    display_name: Optional[str] = None
    ror: Optional[str] = None
    country_code: Optional[str] = None
    type: Optional[str] = None
    lineage: Optional[List[Optional[str]]] = None


class Affiliation(BaseModel):
    raw_affiliation_string: Optional[str] = None
    institution_ids: Optional[List[Optional[str]]] = None


class Authorship(BaseModel):
    author_position: Optional[str] = None
    author: Optional[Author] = None
    institutions: Optional[List[Institution]] = None
    countries: Optional[List[str]] = None
    is_corresponding: Optional[bool] = None
    raw_author_name: Optional[str] = None
    raw_affiliation_strings: Optional[List[str]] = None
    affiliations: Optional[List[Affiliation]] = None


class OpenAccess(BaseModel):
    is_oa: Optional[bool] = None
    oa_status: Optional[str] = None
    oa_url: Optional[str] = None
    any_repository_has_fulltext: Optional[bool] = None


class Source(BaseModel):
    id: Optional[str] = None
    display_name: Optional[str] = None
    issn_l: Optional[str] = None
    issn: Optional[List[str]] = None
    is_oa: Optional[bool] = None
    is_in_doaj: Optional[bool] = None
    is_indexed_in_scopus: Optional[bool] = None
    is_core: Optional[bool] = None
    host_organization: Optional[Any] = None
    host_organization_name: Optional[Any] = None
    host_organization_lineage: Optional[List[Optional[str]]] = None
    host_organization_lineage_names: Optional[List[Optional[str]]] = None
    type: Optional[str] = None


class BestOaLocation(BaseModel):
    is_oa: Optional[bool] = None
    landing_page_url: Optional[str] = None
    pdf_url: Optional[str] = None
    source: Optional[Source] = None
    license: Optional[str] = None
    license_id: Optional[str] = None
    version: Optional[str] = None
    is_accepted: Optional[bool] = None
    is_published: Optional[bool] = None


class Subfield(BaseModel):
    id: Optional[str] = None
    display_name: Optional[str] = None


class Field(BaseModel):
    id: Optional[str] = None
    display_name: Optional[str] = None


class Domain(BaseModel):
    id: Optional[str] = None
    display_name: Optional[str] = None


class Topic(BaseModel):
    id: Optional[str] = None
    display_name: Optional[str] = None
    score: Optional[float] = None
    subfield: Optional[Subfield] = None
    field: Optional[Field] = None
    domain: Optional[Domain] = None


class Keyword(BaseModel):
    id: Optional[str] = None
    display_name: Optional[str] = None
    score: Optional[float] = None


class Source1(BaseModel):
    id: Optional[str] = None
    display_name: Optional[str] = None
    issn_l: Optional[str] = None
    issn: Optional[List[str]] = None
    is_oa: Optional[bool] = None
    is_in_doaj: Optional[bool] = None
    is_indexed_in_scopus: Optional[bool] = None
    is_core: Optional[bool] = None
    host_organization: Optional[str] = None
    host_organization_name: Optional[str] = None
    host_organization_lineage: Optional[List[Optional[str]]] = None
    host_organization_lineage_names: Optional[List[Optional[str]]] = None
    type: Optional[str] = None


class Location(BaseModel):
    is_oa: Optional[bool] = None
    landing_page_url: Optional[str] = None
    pdf_url: Optional[str] = None
    source: Optional[Source1] = None
    license: Optional[str] = None
    license_id: Optional[str] = None
    version: Optional[str] = None
    is_accepted: Optional[bool] = None
    is_published: Optional[bool] = None


class OpenAlexResult(BaseModel):
    title: Optional[str] = None
    ids: Optional[Ids] = None
    language: Optional[str] = None
    publication_date: Optional[str] = None
    authorships: Optional[List[Authorship]] = None
    open_access: Optional[OpenAccess] = None
    best_oa_location: Optional[BestOaLocation] = None
    abstract_inverted_index: Optional[dict[str, list[int]]] = None
    type: Optional[str] = None
    topics: Optional[List[Topic]] = None
    keywords: Optional[List[Keyword]] = None
    referenced_works: Optional[List[str]] = None
    related_works: Optional[List[str]] = None
    locations: Optional[List[Location]] = None


class OpenAlexModel(BaseModel):
    meta: Optional[Meta] = None
    results: Optional[List[OpenAlexResult]] = None
    group_by: Optional[List[Any]] = None
