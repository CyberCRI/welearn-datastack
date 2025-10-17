from abc import ABC

from welearn_database.data.models import ErrorRetrieval, WeLearnDocument


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
