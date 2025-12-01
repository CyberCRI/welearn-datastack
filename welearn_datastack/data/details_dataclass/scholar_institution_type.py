from dataclasses import dataclass
from enum import StrEnum, auto


class InstitutionTypeName(StrEnum):
    # Pre-primary / early childhood education
    PREP = auto()

    # Primary education
    PRIM = auto()

    # Secondary education – general track
    SECU = auto()

    # Secondary education – technical / technological track
    SECT = auto()

    # Secondary education – vocational / professional track
    SEVP = auto()

    # Post-secondary non-tertiary professional/technical institutions
    PRO = auto()

    # Specialized institutions (arts, health, design, agriculture, hospitality, etc.)
    SPC = auto()

    # Higher education – business and management schools
    BUS = auto()

    # Higher education – selective specialized institutions
    # (e.g., French Grandes Écoles, IIT, elite public policy schools)
    SEL = auto()

    # Higher education – comprehensive universities
    UNI = auto()

    OTHER = auto()


@dataclass
class ScholarInstitutionTypeDetails:
    taxonomy_name: InstitutionTypeName
    isced_level_awarded: list[int]
    original_institution_type_name: str
    original_country: str
