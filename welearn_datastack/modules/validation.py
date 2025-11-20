from welearn_database.data.models import WeLearnDocument


def validate_non_null_fields_document(doc: WeLearnDocument) -> bool:
    """
    Validate if a WeLearnDocument has values where it's mandatory after extraction.
    :return: True if valid, False otherwise
    """
    is_desc_empty = not doc.description or doc.description.strip() == ""
    is_content_empty = not doc.full_content or doc.full_content.strip() == ""
    return not (is_desc_empty or is_content_empty)
