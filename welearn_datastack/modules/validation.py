import re

import requests
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.regular_expression import DOI_REGEX


def validate_non_null_fields_document(doc: WeLearnDocument) -> bool:
    """
    Validate if a WeLearnDocument has values where it's mandatory after extraction.
    :return: True if valid, False otherwise
    """
    is_desc_empty = not doc.description or doc.description.strip() == ""
    is_content_empty = not doc.full_content or doc.full_content.strip() == ""
    return not (is_desc_empty or is_content_empty)


def validate_doi(s: str, resolve_doi: bool = True) -> bool:
    """
    Validate if a string is a valid DOI and if it exists.
     - Check if the string matches the DOI format using a regular expression.
     - If it matches, make a request to the DOI API to check if it exists.
     - If the API returns a 200 status code, the DOI is valid and exists; otherwise, it is not valid or does not exist.
     - If the string does not match the DOI format, it is not valid.
     - Handle any exceptions that may occur during the API request and return False in case of an error.
     - Strip the input string and remove the "https://doi.org/" prefix if it exists before validating the DOI format and existence.
     :param s: The string to validate as a DOI.
     :param resolve_doi: Whether to check if the DOI exists by making a request to the DOI API. If False, only the format will be validated.
     :return: True if the string is a valid DOI (and exists if resolve_doi is True), False otherwise.
    """
    s = s.strip().removeprefix("https://doi.org/")
    if not re.match(DOI_REGEX, s):
        return False
    if resolve_doi:
        try:
            r = requests.get(f"https://doi.org/api/handles/{s}", timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False
    return True
