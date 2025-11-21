from typing import List

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
    cues: List[Cue]


class Translation(BaseModel):
    paragraphs: List[Paragraph]


class TEDData(BaseModel):
    video: Video
    translation: Translation


class TEDModel(BaseModel):
    data: TEDData
