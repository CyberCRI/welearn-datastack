from welearn_database.data.models import WeLearnDocument


def validate_non_null_fields_document(doc: WeLearnDocument) -> bool:
    """
    Validate if a WeLearnDocument has values where it's mandatory after extraction.
    :return: True if valid, False otherwise
    """
    desc_in_error = not doc.description or doc.description.strip() == ""
    content_in_error = not doc.full_content or doc.full_content.strip() == ""
    return not (desc_in_error or content_in_error)
