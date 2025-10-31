from typing import List

from pydantic import BaseModel


class Doc(BaseModel):
    docid: str
    title_s: List[str]
    abstract_s: List[str]
    authFullName_s: List[str]
    language_s: List[str]
    uri_s: str
    docType_s: str
    producedDate_tdate: str
    publicationDate_tdate: str
    halId_s: str


class Response(BaseModel):
    numFound: int
    start: int
    numFoundExact: bool
    docs: List[Doc]


class HALModel(BaseModel):
    response: Response
    nextCursorMark: str
