from dataclasses import dataclass


@dataclass
class ScholarLevelDetails:
    isced_level: int  # ISCED 2011 level code
    original_scholar_level_name: str
    original_country: str
