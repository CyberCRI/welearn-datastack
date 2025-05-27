import logging
from typing import List

from keybert import KeyBERT  # type: ignore
from sentence_transformers import SentenceTransformer  # type: ignore

from welearn_datastack.data.db_models import WeLearnDocument
from welearn_datastack.data.enumerations import MLModelsType
from welearn_datastack.modules.embedding_model_helpers import (
    get_document_embedding_model_name_from_lang,
    load_embedding_model,
)
from welearn_datastack.utils_.nlp_utils import tokenize
from welearn_datastack.utils_.path_utils import generate_ml_models_path

logger = logging.getLogger(__name__)

loaded_models: dict[str, SentenceTransformer] = {}


def extract_keywords(document: WeLearnDocument) -> List[str]:
    """
    Extract keywords from a document description
    """
    ml_path = generate_ml_models_path(
        model_type=MLModelsType.EMBEDDING,
        model_name=get_document_embedding_model_name_from_lang(lang=document.lang),  # type: ignore
        extension="",
    )
    embedding_model = load_embedding_model(ml_path.as_posix())
    kw_model = KeyBERT(model=embedding_model)

    clean_description = " ".join(tokenize(str(document.description), document.lang))
    keywords = kw_model.extract_keywords(
        clean_description,
        keyphrase_ngram_range=(1, 2),
        stop_words=[],
        use_mmr=True,
        diversity=0.7,
    )
    keywords = [kw[0] for kw in keywords if kw[1] > 0.5]
    return keywords
