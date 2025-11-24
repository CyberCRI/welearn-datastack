from typing import List, Optional

from pydantic import BaseModel, Field


class Content(BaseModel):
    raw: str
    rendered: str
    protected: bool


class PressBooksModel(BaseModel):
    content: Content
    links_: dict


class EditorItem(BaseModel):
    name: str
    slug: Optional[str]
    type_: str = Field(..., alias="@type")


class AuthorItem(BaseModel):
    name: str
    slug: Optional[str]
    contributor_institution: Optional[str]
    type_: str = Field(..., alias="@type")


class Address(BaseModel):
    type_: str = Field(..., alias="@type")
    addressLocality: str


class Publisher(BaseModel):
    type_: Optional[str] = Field(..., alias="@type")
    name: Optional[str]
    address: Optional[Address]


class License(BaseModel):
    type_: str = Field(..., alias="@type")
    url: str
    name: str


class PressBooksMetadataModel(BaseModel):
    name: str
    isPartOf: str
    editor: Optional[List[EditorItem]]
    author: Optional[List[AuthorItem]]
    publisher: Optional[Publisher]
    datePublished: Optional[str]
    date_gmt: Optional[str]
    modified_gmt: Optional[str]
    license: License
    links_: dict
