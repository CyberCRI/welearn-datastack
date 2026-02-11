from typing import List

from pydantic import BaseModel


class UNESDOCItem(BaseModel):
    url: str
    year: list[str]
    language: list[str]
    title: str
    type: list[str]
    description: str
    subject: list[str]
    creator: str
    rights: str


class UNESDOCRoot(BaseModel):
    total_count: int
    results: list[UNESDOCItem]


class UNESDOCSource(BaseModel):
    DocumentFileName: str
    DocumentType: str
    Document: str


class UNESDOCSources(BaseModel):
    sources: list[UNESDOCSource]
