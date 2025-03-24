from dataclasses import dataclass


@dataclass(frozen=True)
class WikipediaContainer:
    wikipedia_path: str
    depth: int
    lang: str
