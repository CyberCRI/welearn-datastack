from typing import List, Optional

from pydantic import BaseModel, Field


class Content(BaseModel):
    raw: str
    rendered: str
    protected: bool


class PressBooksModel(BaseModel):
    content: Content
    _links: dict


class EditorItem(BaseModel):
    name: str
    slug: str
    _type: str = Field(..., alias="@type")


class AuthorItem(BaseModel):
    name: str
    slug: str
    contributor_institution: Optional[str]
    _type: str = Field(..., alias="@type")


class Address(BaseModel):
    _type: str = Field(..., alias="@type")
    addressLocality: str


class Publisher(BaseModel):
    _type: str = Field(..., alias="@type")
    name: str
    address: Address


class License(BaseModel):
    _type: str = Field(..., alias="@type")
    url: str
    name: str


class PressBooksMetadataModel(BaseModel):
    name: str
    editor: List[EditorItem]
    author: List[AuthorItem]
    publisher: Optional[Publisher]
    datePublished: Optional[str]
    date_gmt: Optional[str]
    modified_gmt: Optional[str]
    license: License
    _links: dict
