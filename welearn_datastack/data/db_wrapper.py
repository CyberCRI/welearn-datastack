from abc import ABC

from welearn_database.data.models import WeLearnDocument


class Wrapper(ABC):
    pass


class WrapperRetrieveDocument(Wrapper):
    def __init__(self, document: WeLearnDocument, is_retrieved: bool):
        self.document = document
        self.is_retrieved = is_retrieved
