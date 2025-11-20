from typing import List, Optional

from pydantic import BaseModel


class Doc(BaseModel):
    docid: str
    title_s: List[str]
    abstract_s: List[str]
    authFullName_s: Optional[List[str]]
    language_s: Optional[List[str]]
    uri_s: str
    docType_s: Optional[str]
    producedDate_tdate: Optional[str]
    publicationDate_tdate: Optional[str]
    halId_s: str


class Response(BaseModel):
    numFound: int
    start: int
    numFoundExact: bool
    docs: List[Doc]


class HALModel(BaseModel):
    response: Response
    nextCursorMark: Optional[str]
