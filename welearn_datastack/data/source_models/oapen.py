from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class CheckSum(BaseModel):
    value: str
    checkSumAlgorithm: str


class Bitstream(BaseModel):
    uuid: str
    name: str
    handle: Any
    type: str
    expand: List[str]
    bundleName: str
    description: Optional[str]
    format: str
    mimeType: str
    sizeBytes: int
    parentObject: Any
    retrieveLink: str
    checkSum: CheckSum
    sequenceId: int
    code: str
    policies: Any
    link: str
    metadata: List[Metadatum]


class Metadatum(BaseModel):
    key: str
    value: str
    language: Optional[str]
    schema_: str
    element: str
    qualifier: Optional[str]
    code: Optional[str] = None


class OapenModel(BaseModel):
    uuid: str
    name: str
    handle: str
    type: str
    expand: List[str]
    lastModified: str
    parentCollection: Any
    parentCollectionList: Any
    parentCommunityList: Any
    bitstreams: List[Bitstream]
    archived: str
    withdrawn: str
    link: str
    metadata: List[Metadatum]
