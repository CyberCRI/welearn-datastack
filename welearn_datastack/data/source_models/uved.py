from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Category(BaseModel):
    title: str
    parent: Optional[Category]
    uid: int
    atat_id: str = Field(..., alias="@id")


class Type(BaseModel):
    title: str
    parent: Optional[Type]
    uid: int
    at_id: str = Field(..., alias="@id")


class Institution(BaseModel):
    name: str
    title: str
    uid: int
    at_id: str = Field(..., alias="@id")


class Keyword(BaseModel):
    title: str
    dewey: str
    uid: int
    at_id: str = Field(..., alias="@id")


class UVEDMemberItem(BaseModel):
    categories: list[Category]
    type: Type
    title: str
    url: Optional[str]
    date: str
    duration: int
    description: str
    contexte: Optional[str]
    slug: str
    transcription: Optional[str] = None
    transcriptionFile: Optional[TranscriptionFile] = None
    kit: Optional[str] = None
    contact: Optional[str] = None
    orignalParent: Optional[str] = None
    secondaryInstitutions: Optional[list[Institution]] = None
    rate: int
    star: int
    mainInstitution: Optional[Institution]
    keywords: list[Keyword]
    uid: int
    at_id: str = Field(..., alias="@id")
    contributor: Optional[list[ContributorItem]] = None


class ContributorItem(BaseModel):
    name: str
    firstName: str
    lastName: str
    title: Optional[str]
    uid: int
    at_id: str = Field(..., alias="@id")


class HydraView(BaseModel):
    hydra_first: str = Field(..., alias="hydra:first")
    hydra_last: str = Field(..., alias="hydra:last")
    hydra_next: Optional[str] = Field(default=None, alias="hydra:next")
    hydra_prev: Optional[str] = Field(default=None, alias="hydra:prev")
    hydra_pages: list[str] = Field(..., alias="hydra:pages")
    hydra_page: int = Field(..., alias="hydra:page")


class HydraMappingItem(BaseModel):
    variable: str
    property: str


class HydraSearch(BaseModel):
    hydra_template: str = Field(..., alias="hydra:template")
    hydra_mapping: list[HydraMappingItem] = Field(..., alias="hydra:mapping")


class RootUVEDModel(BaseModel):
    hydra_member: list[UVEDMemberItem] = Field(..., alias="hydra:member")
    hydra_totalItems: int = Field(..., alias="hydra:totalItems")
    hydra_view: HydraView = Field(..., alias="hydra:view")
    hydra_search: HydraSearch = Field(..., alias="hydra:search")


class File(BaseModel):
    uid: int
    name: str
    mimeType: str
    size: int


class TranscriptionFile(BaseModel):
    uid: int
    url: str
    file: File
