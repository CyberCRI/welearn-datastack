from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class CheckSum(BaseModel):
    value: Optional[str] = None
    checkSumAlgorithm: Optional[str] = None


class Bitstream(BaseModel):
    uuid: Optional[str] = None
    name: Optional[str] = None
    handle: Optional[Any] = None
    type: Optional[str] = None
    expand: Optional[List[str]] = None
    bundleName: Optional[str] = None
    description: Optional[str] = None
    format: Optional[str] = None
    mimeType: Optional[str] = None
    sizeBytes: Optional[int] = None
    parentObject: Optional[Any] = None
    retrieveLink: Optional[str] = None
    checkSum: Optional[CheckSum] = None
    sequenceId: Optional[int] = None
    code: Optional[str] = None
    policies: Optional[Any] = None
    link: Optional[str] = None
    metadata: Optional[List[Metadatum]] = None


class Metadatum(BaseModel):
    key: Optional[str] = None
    value: Optional[str] = None
    language: Optional[str] = None
    schema_: Optional[str] = None
    element: Optional[str] = None
    qualifier: Optional[str] = None
    code: Optional[str] = None


class OapenModel(BaseModel):
    uuid: Optional[str] = None
    name: str
    handle: str
    type: Optional[str] = None
    expand: Optional[List[str]] = None
    lastModified: Optional[str] = None
    parentCollection: Optional[Any] = None
    parentCollectionList: Optional[Any] = None
    parentCommunityList: Optional[Any] = None
    bitstreams: List[Bitstream]
    archived: Optional[str] = None
    withdrawn: Optional[str] = None
    link: Optional[str] = None
    metadata: List[Metadatum]
