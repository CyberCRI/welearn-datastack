from enum import Enum, auto


class PluginType(Enum):
    SCRAPE = 2
    REST = 3


class URLRetrievalType(Enum):
    NEW_MODE = 1
    UPDATE_MODE = 2


class DeletePart(Enum):
    before = 1
    after = 2


class MLModelsType(Enum):
    BI_CLASSIFIER = auto()
    N_CLASSIFIER = auto()
    EMBEDDING = auto()


class WeighedScope(Enum):
    SLICE = auto()
    DOCUMENT = auto()


class Counter(Enum):
    HIT = auto()


class URLStatus(Enum):
    VALID = 1
    UPDATE = 2
    DELETE = 3
    UNKNOWN = 4
