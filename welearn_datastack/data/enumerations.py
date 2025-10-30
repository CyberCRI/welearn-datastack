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


# class Step(Enum):
#     URL_RETRIEVED = "url_retrieved"
#     DOCUMENT_SCRAPED = "document_scraped"
#     DOCUMENT_VECTORIZED = "document_vectorized"
#     DOCUMENT_CLASSIFIED_SDG = "document_classified_sdg"
#     DOCUMENT_CLASSIFIED_NON_SDG = "document_classified_non_sdg"
#     DOCUMENT_KEYWORDS_EXTRACTED = "document_with_keywords"
#     DOCUMENT_IN_QDRANT = "document_in_qdrant"
#     DOCUMENT_IS_INVALID = "document_is_invalid"
#     KEPT_FOR_TRACE = "kept_for_trace"
#     DOCUMENT_IS_IRRETRIEVABLE = "document_is_irretrievable"


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
