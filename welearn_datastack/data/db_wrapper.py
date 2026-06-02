from abc import ABC

from welearn_database.data.models import ErrorRetrieval, WeLearnDocument

from welearn_datastack.data.source_models.hal import HALModel
from welearn_datastack.data.source_models.oapen import OapenModel
from welearn_datastack.data.source_models.open_alex import OpenAlexResult
from welearn_datastack.data.source_models.ted import TEDModel
from welearn_datastack.data.source_models.world_bank_okr import WorldBankOKRRecord


class Wrapper(ABC):
    pass


class WrapperRetrieveDocument(Wrapper):
    def __init__(
        self,
        document: WeLearnDocument,
        http_error_code: int | None = None,
        error_info: str | None = None,
    ):
        self.document = document
        self.http_error_code = http_error_code
        self.error_info = error_info

    @property
    def is_error(self) -> bool:
        is_valid = self._validate_non_null_fields_document()
        return (
            self.http_error_code is not None
            or self.error_info is not None
            or not is_valid
        )

    def to_error_retrieval(self) -> ErrorRetrieval:
        return ErrorRetrieval(
            document_id=self.document.id,
            http_error_code=self.http_error_code,
            error_info=self.error_info,
        )

    def _validate_non_null_fields_document(self) -> bool:
        """
        Validate if a WeLearnDocument has values where it's mandatory after extraction.
        :return: True if valid, False otherwise
        """
        is_desc_empty = (
            not self.document.description or self.document.description.strip() == ""
        )
        is_content_empty = (
            not self.document.full_content or self.document.full_content.strip() == ""
        )
        is_valid = not (is_desc_empty or is_content_empty)
        if self.error_info is not None:
            self.error_info.error_info = "Mandatory fields are missing after extraction"
        return is_valid


class WrapperRawData(Wrapper):
    def __init__(
        self,
        raw_data: (
            OapenModel | HALModel | OpenAlexResult | TEDModel | WorldBankOKRRecord
        ),
        document: WeLearnDocument,
    ):
        self.raw_data = raw_data
        self.document = document
