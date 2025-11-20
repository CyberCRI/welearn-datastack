from typing import List, Optional

from pydantic import BaseModel


class Type(BaseModel):
    name: str


class Video(BaseModel):
    description: str
    internalLanguageCode: str
    presenterDisplayName: str
    duration: int
    title: str
    publishedAt: str
    canonicalUrl: str
    type: Type


class Cue(BaseModel):
    text: str


class Paragraph(BaseModel):
    cues: Optional[List[Cue]] = None


class Translation(BaseModel):
    paragraphs: Optional[List[Paragraph]] = None


class TEDData(BaseModel):
    video: Optional[Video] = None
    translation: Optional[Translation] = None


class TEDModel(BaseModel):
    data: Optional[TEDData] = None
