from dataclasses import dataclass


@dataclass
class ScholarLevelDetails:
    isced_level: int
    original_scholar_level_name: str
    original_country: str
