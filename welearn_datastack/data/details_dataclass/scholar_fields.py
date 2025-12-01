from dataclasses import dataclass


@dataclass
class ScholarFieldsDetails:
    isced_field: int  # ISCED-F 2013 field code
    original_scholar_field_name: str
    original_country: str
