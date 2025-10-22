from abc import ABC

from welearn_database.data.models import ErrorRetrieval, WeLearnDocument

from welearn_datastack.data.source_models.hal import HALModel
from welearn_datastack.data.source_models.oapen import OapenModel
from welearn_datastack.data.source_models.open_alex import OpenAlexResult


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
        return self.http_error_code is not None or self.error_info is not None

    def to_error_retrieval(self) -> ErrorRetrieval:
        return ErrorRetrieval(
            document_id=self.document.id,
            http_error_code=self.http_error_code,
            error_info=self.error_info,
        )


class WrapperRawData(Wrapper):
    def __init__(
        self,
        raw_data: OapenModel | HALModel | OpenAlexResult,
        document: WeLearnDocument,
    ):
        self.raw_data = raw_data
        self.document = document
