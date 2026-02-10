from typing import List

from pydantic import BaseModel


class UNESDOCItem(BaseModel):
    url: str
    year: List[str]
    language: List[str]
    title: str
    type: List[str]
    description: str
    subject: List[str]
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
